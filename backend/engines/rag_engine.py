from backend.wrappers import vector_storage_wrapper, S3_wrapper, llm_wrapper
from backend.utils.llm_security import LLMSecurityManager
from langchain_community.document_loaders import PyPDFLoader
from langchain.schema import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

import glob
import os
import sys
from datetime import datetime
from uuid import uuid4
from collections import defaultdict

from dotenv import load_dotenv
load_dotenv()

class RagEngine:
    def __init__(self):
        # Initialize vector storage
        self.vector_store = vector_storage_wrapper.VectorStorage(table_name="documents_collection", k=5)
        
        # Initialize security
        self.security_manager = LLMSecurityManager()
        
        # Configuration
        self.DATA_PATH = os.path.join(os.path.dirname(__file__), '../data/rag-uploads')
        self.SIMILARITY_THRESHOLD = 0.7
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=100,
            length_function=len,
            is_separator_regex=False,
        )
        
        # Ensure directories exist
        os.makedirs(self.DATA_PATH, exist_ok=True)
    
    def get_answer_with_rag(self, user_msg, system_prompt, provider='groq', fallback=None):
        """Get answer with RAG knowledge retrieval and LLM call"""
        
        # Sanitize user input
        security_result = self.security_manager.secure_prompt(user_msg)
        if security_result['should_block']:
            return "I'm sorry, but I cannot process this request due to security concerns.", []
        
        sanitized_user_msg = security_result['processed_input']
        
        # Retrieve relevant knowledge from vector store
        knowledge_results = self.vector_store.invoke(sanitized_user_msg)
        collected_knowledge = ""
        if knowledge_results:
            # Format the knowledge
            knowledge_texts = []
            for doc in knowledge_results:
                if hasattr(doc, 'page_content'):
                    knowledge_texts.append(doc.page_content)
                elif isinstance(doc, dict) and 'content' in doc:
                    knowledge_texts.append(doc['content'])
                elif isinstance(doc, str):
                    knowledge_texts.append(doc)
            
            collected_knowledge = "\n\n".join(knowledge_texts)
        
        # Append knowledge to system prompt
        if collected_knowledge:
            enhanced_system_prompt = system_prompt + f"\n\nKnowledge: {collected_knowledge}"
        else:
            enhanced_system_prompt = system_prompt
        
        # Prepare messages for LLM
        messages = [
            {'role': 'system', 'content': enhanced_system_prompt},
            {'role': 'user', 'content': sanitized_user_msg}
        ]
        
        # Call LLM
        llm_result = llm_wrapper.chat(provider, messages, [], fallback)
        reply = llm_result.get('reply', 'No response from LLM')
        
        # Sanitize response
        response_security = self.security_manager.secure_response(reply)
        sanitized_reply = response_security['processed_response']
        
        return sanitized_reply, []  # No sources for now
    
    def _collect_DB_context(self, session_id):
        return
    
    def _collect_VDB_knowdledge(self, session_id):
        return
    
    def _engineer_prompt(self, user_msg):
        return
    
    def _clean_input(self, user_msg):
        return
    
    def clean_output(self, output):
        return
    
    def load_full_documents_from_dir(self, directory_path):
        documents = []
        for filename in os.listdir(directory_path):
            if filename.endswith(".pdf"):
                path = os.path.join(directory_path, filename)
                loader = PyPDFLoader(path)
                pages = loader.load()

                # Combine all pages into one full document
                full_text = "\n".join([p.page_content for p in pages])

                # Use metadata from the first page
                metadata = pages[0].metadata
                metadata["title"] = metadata.get("title") or filename[:-4]
                metadata["source"] = path
                try:
                    metadata["timestamp"] = os.path.getmtime(path)
                except Exception:
                    metadata["timestamp"] = None

                # Create combined document
                documents.append(Document(page_content=full_text, metadata=metadata))
        return documents

    def prepare_new_RAG_pdf_pipeline(self):
        raw_documents = self.load_full_documents_from_dir(self.DATA_PATH)
        output_metadata = {}

        for doc in raw_documents:
            title = doc.metadata["title"]
            timestamp = doc.metadata["timestamp"]

            # Check for similar documents in vector store
            similar_docs = self.vector_store.query_pgvector(doc.page_content, k=5)
            conflicts = []

            for existing_doc in similar_docs:
                if existing_doc.metadata.get("title") == title:
                    conflicts.append({
                        "conflicting_with": title,
                        "existing_timestamp": existing_doc.metadata.get("timestamp", "unknown")
                    })

            if not conflicts:
                output_metadata[title] = {
                    "status": "no_conflicts",
                    "new_timestamp": timestamp
                }
            else:
                output_metadata[title] = {
                    "status": "conflicts_found",
                    "conflicts": conflicts,
                    "new_timestamp": timestamp
                }
                
        return output_metadata

    def clear_folder(self, target_path):
        pattern = os.path.join(target_path, '*')  

        for filepath in glob.glob(pattern):
            # ensure it's a file, not a subdir
            if os.path.isfile(filepath):
                os.remove(filepath)

    def load_RAG_pdf_pipeline(self, conflict_resolutions=None):
        """
        Process and load PDF documents into the vector store.
        
        Args:
            conflict_resolutions: Dictionary with decisions about conflicting files
                                 {filename: "keep" or "skip"}
        """
        raw_documents = self.load_full_documents_from_dir(self.DATA_PATH)
        processed_documents = []
        
        # If no conflict resolutions provided, process all documents
        if conflict_resolutions is None:
            processed_documents = raw_documents
        else:
            for doc in raw_documents:
                title = doc.metadata["title"]
                # If document has a resolution, check it
                if title in conflict_resolutions:
                    if conflict_resolutions[title] == "keep":
                        processed_documents.append(doc)
                # Skip if resolution is "skip"
                else:
                    # If no resolution specified for this document, include it
                    processed_documents.append(doc)
        
        if not processed_documents:
            return "No documents to process after conflict resolution."
        
        chunks = self.text_splitter.split_documents(processed_documents)
        
        uuids = [str(uuid4()) for _ in range(len(chunks))]
        
        self.vector_store.add_documents(documents=chunks, ids=uuids)
        
        # Upload to S3
        for doc in processed_documents:
            S3_wrapper.upload_file_to_s3(doc.metadata["source"])
            
        self.clear_folder(self.DATA_PATH)

        return f"Documents processed and uploaded successfully. {len(processed_documents)} uploaded. {len(chunks)} chunks created from {len(processed_documents)} documents and added to the knowledge database."
    
    def list_documents(self):
        """List all documents in the knowledge base"""
        s3_files = S3_wrapper.list_files_in_s3()
        return [{"filename": os.path.basename(f), "s3_key": f} for f in s3_files]
    
    def delete_document(self, document_name):
        """Delete a document from both vector store and S3"""
        # Delete from vector store
        deleted_count = self.vector_store.delete_documents_by_metadata({"title": document_name})
        
        # Delete from S3 - s3_key is the filename with .pdf
        s3_key = document_name if document_name.endswith('.pdf') else f"{document_name}.pdf"
        S3_wrapper.delete_file_from_s3(s3_key)
        
        return f"Deleted {deleted_count} chunks for document '{document_name}' from vector store and removed from S3."
    
