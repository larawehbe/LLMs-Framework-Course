from pipeline import CompleteRAGPipeline
from utils import build_pdf_docs, test_pymupdf

from dotenv import load_dotenv
import os
load_dotenv()




if __name__ == "__main__":

    pipeline = CompleteRAGPipeline(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        pinecone_api_key=os.getenv("PINECONE_API")
    )

    pdf_path = "data/"

    # docs = build_pdf_docs(pdf_path)

    # print(f"Found {len(docs)} PDF documents to ingest.")
    # try:
    #     print("\nChunking all documents...")
    #     chunks = pipeline.chunk_all_documents(docs)
    # except Exception as e:
    #     print("Error during document chunking:", e)
    #     raise e

    # try:
    #     print("\nCreating embeddings for all chunks...")
    #     chunks_with_embeddings = pipeline.create_embeddings(chunks)
    # except Exception as e:
    #     print("Error during embedding creation:", e)
    #     raise e

    # try:
    #     print("\nStoring chunks in vector database...")
    #     pipeline.store_in_vectordb(chunks_with_embeddings)
    #     print("="*70)
    #     print("🎉 SETUP COMPLETE! Vector database is ready for queries.")
    #     print("="*70)
    # except Exception as e:  
    #     print("Error during storage in vector database:", e)
    #     raise e
    



    while True:
        x = input("Ask your question (or type 'exit' to quit): ")
        if x.lower() == 'exit':
            print("Exiting the question loop. Goodbye!")
            break
        try:
            result = pipeline.answer_question(x)
            print(f"Answer: {result['answer']}")
            print(f"\nCitations (score-ranked):")
            for cite in result['citations']:
                source_info = f"  📄 {cite['source_type'].upper()}: {cite['doc_id']}"
                if cite.get('section'):
                    source_info += f" - {cite['section']}"
                if cite.get('page'):
                    source_info += f" (Page {cite['page']})"
                if cite.get('ticket_id'):
                    source_info += f" [Ticket: {cite['ticket_id']}]"
                source_info += f" | Confidence: {cite['confidence_score']}"
                print(source_info)
            print("\n" + "-" * 50 + "\n")
        except Exception as e:
            print("An error occurred while answering the question:", e)

    