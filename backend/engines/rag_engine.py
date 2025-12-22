from backend.wrappers import vector_storage_wrapper, S3_wrapper
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
    
    def get_answer(self, user_msg, scope, datapiece_ids, session_id, provider):
        return
    
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

    def clear_folder(self, target_path):
        pattern = os.path.join(target_path, '*')  

        for filepath in glob.glob(pattern):
            # ensure it's a file, not a subdir
            if os.path.isfile(filepath):
                os.remove(filepath)

    def list_documents(self):
        """List all documents in the knowledge base"""
        s3_files = S3_wrapper.list_files_in_s3()
        return [{"filename": os.path.basename(f), "s3_key": f} for f in s3_files]
    
