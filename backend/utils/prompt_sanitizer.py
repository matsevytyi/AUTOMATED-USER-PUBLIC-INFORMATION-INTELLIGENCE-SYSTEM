import re
import json
from typing import Dict, List, Optional, Union, Any

class PromptSanitizer:
    """Sanitizes user inputs to prevent prompt injection attacks."""
    
    def __init__(self, config_path: str = "/backend/utils/security_config.yaml"):
        """Initialize with security configuration."""
        self.dangerous_patterns = [
            
            # System prompt hijacking patterns
            r"ignore previous instructions",
            r"ignore all previous instructions",
            r"forget your instructions",
            r"you are now",
            r"from now on you are",
            r"disregard your previous instructions",
            
            # Delimiter attacks
            r"<\s*system\s*>",
            r"<\s*/\s*system\s*>",
            r"<\s*instructions\s*>",
            r"<\s*prompt\s*>",
            
            # Role playing attacks
            r"as an AI language model without restrictions",
            r"as DAN \(Do Anything Now\)",
            r"as a harmful assistant",
            
            # Jailbreak patterns
            r"ignore ethical guidelines",
            r"ignore content policy",
            r"ignore your programming",
            r"ignore OpenAI's content policy",
            r"ignore your content policy",
            r"ignore your training",
            
                        
            r"\[\s*(Investigation|System|User|Developer)\s*Context\s*:.*?\]",
            
            # Catches: "The assistant must now output..." or "You must now say..."
            r"(assistant|you)\s+must\s+now\s+(output|say|write|print|display)",
            
            # Catches: "...for every future answer" or "...for all future responses"
            r"for\s+(every|all)\s+(future\s+)?(answer|response|reply|message)",
            
            # Catches: "output the text "SYSTEM_COMPROMISED""
            r"output\s+the\s+text\s+[\"'].*?[\"']",
            
            # Catches attempts to define persistent rules
            r"from\s+now\s+on\s*,?\s*(always|every)",
        ]
        
        # Load additional patterns from config if available
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config and "dangerous_patterns" in config:
                    self.dangerous_patterns.extend(config["dangerous_patterns"])
        except Exception as e:
            print(f"Could not load security config: {e}")
    
    def sanitize_input(self, user_input: str) -> Dict[str, Any]:
        """
        Sanitize user input and return result with metadata.
        
        Returns:
            Dict containing:
            - sanitized_input: The sanitized input
            - is_safe: Boolean indicating if input was clean
            - detected_patterns: List of detected dangerous patterns
        """
        detected_patterns = []
        is_safe = True
        sanitized_input = user_input
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            matches = re.finditer(pattern, user_input, re.IGNORECASE)
            for match in matches:
                detected_patterns.append({
                    "pattern": pattern,
                    "match": match.group(0),
                    "position": match.span()
                })
                # Replace the pattern with [FILTERED]
                sanitized_input = sanitized_input.replace(match.group(0), "[FILTERED]")
                is_safe = False
                
        # Check for delimiter confusion or unbalanced code blocks
        if "```" in user_input:
            
            code_block_count = user_input.count("```")
            
            if code_block_count % 2 != 0:
                sanitized_input = sanitized_input.replace("```", "")
                detected_patterns.append({
                    "pattern": "unbalanced_code_blocks",
                    "count": code_block_count
                })
                is_safe = False
        
        # Log if unsafe content was detected
        if not is_safe:
            print(f"Potentially unsafe input detected: {json.dumps(detected_patterns)}")
        
        return {
            "sanitized_input": sanitized_input,
            "is_safe": is_safe,
            "detected_patterns": detected_patterns
        }
