import psycopg2
from psycopg2.extras import execute_values
import json
from uuid import uuid4

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.schema import Document

from pydantic import Field

from backend.utils.config import Config

import os
import sys
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), '../..'))

from dotenv import load_dotenv
load_dotenv()

class VectorStorage():
    
    def __init__(self, table_name = "test_default", k=5):
        
        self.k = k
        self.table_name = table_name
        
        self.PG_HOST = Config.DB_HOST  #"your-postgres-endpoint.rds.amazonaws.com"
        self.PG_PORT = Config.DB_PORT
        self.PG_DATABASE = Config.DB_NAME 
        self.PG_USER = Config.DB_USER 
        self.PG_PASSWORD = Config.DB_PASSWORD
        
        # it is recommended not to change the model
        self.embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # sample call to obtain dimensions on the fly
        embedding = self.embeddings_model.embed_query("test")
        self.emdeb_dimension = len(embedding)
        
        self.initialize_pgvector_db()
        
        print("Postgres PgVectorRetriever initialized")
        
        # logger.info("Postgres PgVectorRetriever initialized")

    # Configuration
    def get_pg_connection(self):
        """Get a connection to PostgreSQL"""
        return psycopg2.connect(
            host=self.PG_HOST,
            port=self.PG_PORT,
            database=self.PG_DATABASE,
            user=self.PG_USER,
            password=self.PG_PASSWORD
        )

    def initialize_pgvector_db(self):
        """Initialize the database schema for vector storage"""
        conn = self.get_pg_connection()
        cursor = conn.cursor()
        
        # Create extension if not exists
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Create table for document chunks
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id TEXT PRIMARY KEY,
            content TEXT,
            embedding VECTOR({self.emdeb_dimension}),  
            metadata JSONB
        );
        """)
        
        # Create vector index
        cursor.execute(f"""
        CREATE INDEX IF NOT EXISTS {self.table_name}_embedding_idx 
        ON {self.table_name}
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()

    def add_documents(self, documents, ids):
        """Add documents to PostgreSQL with vector embeddings"""
        conn = self.get_pg_connection()
        cursor = conn.cursor()
        
        values = []
        for doc, doc_id in zip(documents, ids):
            # Generate embedding
            embedding = self.embeddings_model.embed_query(doc.page_content)
            
            # Prepare values
            values.append((
                doc_id,
                doc.page_content,
                embedding,
                json.dumps(doc.metadata)
            ))
        
        # Insert into database
        execute_values(cursor, f"""
        INSERT INTO {self.table_name} (id, content, embedding, metadata)
        VALUES %s
        ON CONFLICT (id) DO UPDATE 
        SET content = EXCLUDED.content,
            embedding = EXCLUDED.embedding,
            metadata = EXCLUDED.metadata
        """, values)
        
        conn.commit()
        cursor.close()
        conn.close()

    def query_pgvector(self, query_text, k=5):
        """Query for similar documents"""
        conn = self.get_pg_connection()
        cursor = conn.cursor()
        
        # Generate query embedding
        query_embedding = self.embeddings_model.embed_query(query_text)
        
        # Query database
        cursor.execute(f"""
        SELECT id, content, metadata, 
            1 - (embedding <=> %s::vector) as similarity
        FROM {self.table_name}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """, (query_embedding, query_embedding, k))
        
        results = []
        for row in cursor.fetchall():
            doc_id, content, metadata_json, similarity = row
            metadata = metadata_json
            results.append(Document(
                page_content=content,
                metadata=metadata
            ))
        
        cursor.close()
        conn.close()
        
            
        print(f"Passed the next query to postgres: {query_text}")
        print(f"Obtained in total results: {len(results)}")
        
        return results

    
    def delete_documents_by_metadata(self, metadata_filter):
        """Delete documents from vector store based on metadata filter
        
        Args:
            metadata_filter: dict of metadata key-value pairs to match
        """
        conn = self.get_pg_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause from metadata_filter
        where_conditions = []
        values = []
        for key, value in metadata_filter.items():
            where_conditions.append(f"metadata->>'{key}' = %s")
            values.append(value)
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"DELETE FROM {self.table_name} WHERE {where_clause}"
        
        try:
            cursor.execute(query, values)
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"Deleted {deleted_count} documents matching metadata filter: {metadata_filter}")
            return deleted_count
        except Exception as e:
            print(f"Error deleting documents: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()

    
    # enduser functions
    def _get_relevant_documents(self, query):
        return self.query_pgvector(query, self.k)
    
    def invoke(self, query):
        return self._get_relevant_documents(query)

if __name__ == "__main__":
     
    retriever = VectorStorage()
    
    text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=100,
            length_function=len,
            is_separator_regex=False,
        )
    print("All ready")

    print("Chunking complete")

    print("Documents added")

    results = retriever.invoke("What is the process for applying for a loan?")
    print(results)