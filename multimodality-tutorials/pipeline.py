"""
Complete end-to-end RAG pipeline:
1. Chunk documents
2. Create embeddings
3. Store in vector DB
4. Semantic search
5. Generate answers with citations
"""

import json
from typing import List, Dict
from openai import OpenAI
import pinecone
from pinecone import Pinecone, ServerlessSpec

# Import chunking functions from previous code
from ingest_data import chunk_pdf_visuals_improved, chunk_pdf_text

class CompleteRAGPipeline:
    """
    End-to-end pipeline from documents to semantic search answers.
    """
    
    def __init__(self, openai_api_key: str, pinecone_api_key: str):
        """
        Initialize embedding model and vector database.
        """
        # OpenAI for embeddings and LLM
        self.openai_client = OpenAI(api_key=openai_api_key)
        
        # Pinecone for vector storage
        self.pc = Pinecone(api_key=pinecone_api_key)
        self.index_name = "deepseek-paper"
        
        # Create index if it doesn't exist
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=1536,  # OpenAI embedding dimension
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-east-1')
            )
        
        self.index = self.pc.Index(self.index_name)
    
    # ========================================================================
    # STEP 1: Chunk all documents
    # ========================================================================
    
    def chunk_all_documents(self, pdf_docs: List[Dict]) -> List[Dict]:
        """
        Chunk all document types.
        
        Args:
            pdf_docs: List of {pdf_path, doc_id, metadata}
            faq_path: Path to faq.json
            tickets_path: Path to tickets_resolved.txt
        
        Returns:
            List of all chunks
        """
        all_chunks = []
        
        print("📄 Chunking PDFs...")
        for doc in pdf_docs:
            # Text chunks
            text_chunks = chunk_pdf_text(
                doc['pdf_path'], doc['doc_id'], doc['metadata']
            )
            all_chunks.extend(text_chunks)
            
            visual_chunks = chunk_pdf_visuals_improved(doc['pdf_path'], doc['doc_id'], doc['metadata'], self.openai_client)

            all_chunks.extend(visual_chunks)
            
        
        
        print(f"\n✅ Total chunks: {len(all_chunks)}")
        
        return all_chunks
    
    # ========================================================================
    # STEP 2: Create embeddings
    # ========================================================================
    
    def create_embeddings(self, chunks: List[Dict]) -> List[Dict]:
        """
        Create vector embeddings for all chunks.
        This is what enables semantic search!
        
        Args:
            chunks: List of chunks from step 1
        
        Returns:
            Chunks with 'embedding' field added
        """
        print("🧮 Creating embeddings...")
        
        # Process in batches (OpenAI limit is 2048 texts per request)
        batch_size = 100
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk['text'] for chunk in batch]
            
            # Create embeddings using OpenAI
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",  # or text-embedding-ada-002
                input=texts
            )
            
            # Add embeddings to chunks
            for j, chunk in enumerate(batch):
                chunk['embedding'] = response.data[j].embedding
            
            print(f"  Progress: {min(i + batch_size, len(chunks))}/{len(chunks)}")
        
        print("✅ Embeddings created!\n")
        return chunks
    
    # ========================================================================
    # STEP 3: Store in vector database
    # ========================================================================
    
    def store_in_vectordb(self, chunks: List[Dict]):
        """
        Upload chunks with embeddings to Pinecone.
        This enables fast semantic search.
        
        Args:
            chunks: Chunks with embeddings from step 2
        """
        print("💾 Storing in vector database...")
        
        # Prepare vectors for Pinecone
        vectors = []
        for idx, chunk in enumerate(chunks):
            # Flatten metadata - Pinecone doesn't support nested dicts
            flat_metadata = {
                'text': chunk['text'][:1000],  # Store text snippet
                'source_type': chunk['metadata'].get('source_type', ''),
                'content_type': chunk['metadata'].get('content_type', ''),
                'doc_id': chunk['metadata'].get('doc_id', ''),
                'page': chunk['metadata'].get('page', 0),
            }
            
            # Remove empty values
            flat_metadata = {k: v for k, v in flat_metadata.items() if v}
            
            vectors.append({
                'id': f"chunk_{idx}",
                'values': chunk['embedding'],
                'metadata': flat_metadata
            })
        
        # Upsert in batches
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch)
            print(f"  Uploaded: {min(i + batch_size, len(vectors))}/{len(vectors)}")
        
        print("✅ All chunks stored in vector DB!\n")
    
    # ========================================================================
    # STEP 4: Semantic search
    # ========================================================================
    
    def search(self, query: str, filters: Dict = None, top_k: int = 5) -> List[Dict]:
        """
        Semantic search across all documents.
        THIS IS THE MAGIC - finds relevant content by meaning, not keywords!
        
        Args:
            query: User's question
            filters: Optional filters (region='UAE', lang='en', etc.)
            top_k: Number of results
        
        Returns:
            List of relevant chunks with scores
        """
        # Create embedding for the query
        query_embedding = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query
        ).data[0].embedding
        
        # Search vector DB
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filters  # e.g., {'region': 'UAE', 'lang': 'en'}
        )
        
        # Format results
        found_chunks = []
        for match in results['matches']:
            found_chunks.append({
                'text': match['metadata']['text'],
                'score': match['score'],
                'metadata': match['metadata']
            })
        
        return found_chunks
    
    # ========================================================================
    # STEP 5: Generate answer with citations
    # ========================================================================
    
    def answer_question(self, query: str, filters: Dict = None) -> Dict:
        """
        Complete RAG: Search + Generate answer with citations.
        
        Args:
            query: User's question
            filters: Optional filters
        
        Returns:
            {
                'answer': str,
                'citations': List[Dict],
                'sources': List[Dict]
            }
        """
        # Search for relevant chunks
        search_results = self.search(query, filters=filters, top_k=5)
        
        if not search_results:
            return {
                'answer': "I couldn't find relevant information in the documents.",
                'citations': [],
                'sources': []
            }
        
        # Build context from search results
        context_parts = []
        for idx, result in enumerate(search_results):
            meta = result['metadata']
            
            # Format source information
            doc_id = meta.get('doc_id', 'Unknown')
            page = meta.get('page', 'N/A')
            section = meta.get('section', '')
            content_type = meta.get('content_type', 'text')
            
            source_info = f"{doc_id}"
            if page and page != 'N/A':
                source_info += f", Page {page}"
            if section:
                source_info += f", Section: {section}"
            if content_type in ['table', 'image']:
                source_info += f" [{content_type.upper()}]"
            
            context_parts.append(
                f"[Source {idx}] {source_info}\n{result['text']}\n"
            )
        
        context = "\n---\n".join(context_parts)
        
        # Generate answer using LLM
        prompt = f"""You are a helpful customer support assistant. Answer the question using ONLY the provided context.

            IMPORTANT:
            - Always cite your sources using [Source X] notation
            - Include document ID and page number in citations
            - If the answer is not in the context, say so
            - Be concise but complete

            CONTEXT:
            {context}

            QUESTION: {query}

            Answer with citations:"""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise customer support assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        answer = response.choices[0].message.content
        
        # Extract citations based on scores and source mentions
        # Strategy: Include top sources with score > 0.6 OR explicitly mentioned
        citations = []
        
        for idx, result in enumerate(search_results):
            meta = result['metadata']
            score = result['score']
            
            # Include if: high confidence (>0.6) OR explicitly cited in answer
            is_high_confidence = score > 0.6
            is_explicitly_cited = f"[Source {idx}]" in answer or f"Source {idx}" in answer
            
            if is_high_confidence or is_explicitly_cited:
                citation = {
                    'source_id': idx,
                    'doc_id': meta.get('doc_id', 'Unknown'),
                    'section': meta.get('section', ''),
                    'source_type': meta.get('source_type', ''),
                    'content_type': meta.get('content_type', ''),
                    'confidence_score': round(score, 3)
                }
                
                # Add page only if it exists and is valid
                page = meta.get('page')
                if page and page not in [0, 'N/A', None]:
                    citation['page'] = int(page) if isinstance(page, float) else page
                
                # Add ticket_id if it's a ticket
                if meta.get('ticket_id'):
                    citation['ticket_id'] = meta.get('ticket_id')
                
                # Add faq_id if it's an FAQ
                if meta.get('faq_id') is not None:
                    citation['faq_id'] = meta.get('faq_id')
                
                citations.append(citation)
        
        # Sort citations by confidence score (highest first)
        citations.sort(key=lambda x: x['confidence_score'], reverse=True)
        
        # Limit to top 3 citations to avoid clutter
        citations = citations[:3]
        
        return {
            'answer': answer,
            'citations': citations,
            'sources': search_results
        }

