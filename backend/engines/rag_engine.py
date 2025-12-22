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
    
