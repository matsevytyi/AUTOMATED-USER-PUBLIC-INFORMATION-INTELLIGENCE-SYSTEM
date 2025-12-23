import re
import json
import hashlib
from typing import Dict, List, Any, Optional, Union
from .prompt_sanitizer import PromptSanitizer


class LLMSecurityManager:
    """Manages security for LLM interactions."""
    
    def __init__(self, config_path: str = "/backend/utils/security_config.yaml"):
        """Initialize security components."""
        self.prompt_sanitizer = PromptSanitizer()
        self.request_history = {}
        self.max_history_size = 1000
        self.sensitive_patterns = []
        
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config and "sensitive_patterns" in config:
                    self.sensitive_patterns.extend(config["sensitive_patterns"])
                    
        except Exception as e:
            print(f"Could not load security config: {e}")
        
    def secure_prompt(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input to ensure it's safe for LLM processing.
        
        Args:
            user_input: Raw user input
            
        Returns:
            Dict containing security processing results
        """
        
        # Sanitize the input
        sanitize_result = self.prompt_sanitizer.sanitize_input(user_input)
        
        # Check for sensitive information
        sensitive_info = self._detect_sensitive_info(user_input)
        
        # Track request for rate limiting
        request_id = self._track_request(user_input)
        
        # Determine if the request should be blocked and extend if needed
        # Sanitize input is not counted because it's already sanitized
        should_block = not sanitize_result["is_safe"]
        
        # Prepare final result
        result = {
            "processed_input": sanitize_result["sanitized_input"],
            "is_safe": sanitize_result["is_safe"] and not sensitive_info["contains_sensitive"],
            "should_block": should_block,
            "security_metadata": {
                "request_id": request_id,
                "injection_attempts": sanitize_result["detected_patterns"],
                "sensitive_info": sensitive_info["detected_items"],
                "security_actions": []
            }
        }
        
        # Add security actions
        if not sanitize_result["is_safe"]:
            result["security_metadata"]["security_actions"].append({
                "action": "blocked_request",
                "reason": "potential_prompt_injection"
            })
            
        if sensitive_info["contains_sensitive"]:
            result["security_metadata"]["security_actions"].append({
                "action": "sanitized_input",
                "reason": "sensitive_information_detected"
            })
            
        # Log security events
        if not result["is_safe"]:
            print(f"Security issue detected: {json.dumps(result['security_metadata'])}")
            
        return result
    
    def secure_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Process LLM response to ensure it's safe for user consumption.
        
        Args:
            llm_response: Raw LLM response
            
        Returns:
            Dict containing processed response and metadata
        """
        # Check for sensitive information leakage
        sensitive_info = self._detect_sensitive_info(llm_response)
        
        processed_response = llm_response
        
        # Redact any sensitive information
        if sensitive_info["contains_sensitive"]:
            processed_response = self._redact_sensitive_info(
                llm_response, 
                sensitive_info["detected_items"]
            )
            print(f"Sensitive information detected in LLM response and redacted")
        
        return {
            "processed_response": processed_response,
            "contains_sensitive": sensitive_info["contains_sensitive"],
            "security_metadata": {
                "sensitive_info": sensitive_info["detected_items"]
            }
        }
    
    def _detect_sensitive_info(self, text: str) -> Dict[str, Any]:
        """Detect sensitive information in text."""
        detected_items = []
        
        for item in self.sensitive_patterns:
            
            pattern = item["pattern"]
            pattern_name = item["name"]

            matches = re.finditer(pattern, text)
            for match in matches:
                detected_items.append({
                    "pattern_id": pattern_name,
                    "position": match.span()
                })
        
        return {
            "contains_sensitive": len(detected_items) > 0,
            "detected_items": detected_items
        }
    
    def _redact_sensitive_info(self, text: str, detected_items: List[Dict[str, Any]]) -> str:
        """Redact sensitive information from text."""
        
        # Sort detected items by position in reverse order to avoid index shifting
        sorted_items = sorted(detected_items, key=lambda x: x["position"], reverse=True)
        
        # mutable list of characters
        chars = list(text)
        
        # Replace sensitive information with [REDACTED]
        for item in sorted_items:
            start, end = item["position"]
            redacted_text = "[REDACTED]"
            chars[start:end] = redacted_text
        
        return ''.join(chars)
    
    def _track_request(self, user_input: str) -> str:
        """Track request for rate limiting and pattern detection."""
        # Create a unique identifier for this request
        request_hash = hashlib.md5(user_input.encode()).hexdigest()
        
        # Clean up history if it gets too large
        if len(self.request_history) > self.max_history_size:
            # Remove oldest entries
            oldest_keys = sorted(self.request_history.keys())[:100]
            for key in oldest_keys:
                del self.request_history[key]
        
        # Store request
        import time
        self.request_history[request_hash] = {
            "timestamp": time.time(),
            "input_length": len(user_input)
        }
        
        return request_hash


