from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from agno.db.postgres.postgres import PostgresDb

import asyncio
from dotenv import load_dotenv
load_dotenv()   

knowledge = Knowledge(
    vector_db=PgVector(
        table_name="vectors",
        db_url="postgresql+psycopg://ai:ai@localhost:5532/ai"
    )
)

contents_db = PostgresDb(
    db_url="postgresql+psycopg://ai:ai@localhost:5532/ai",
    knowledge_table="knowledge_contents",
)

# Create Knowledge Instance
knowledge = Knowledge(
    name="Basic SDK Knowledge Base",
    description="Agno 2.0 Knowledge Implementation",
    contents_db=contents_db,
    vector_db=PgVector(
        table_name="vectors", db_url="postgresql+psycopg://ai:ai@localhost:5532/ai"
    ),
)

# Add content from URL
# knowledge.add_content(
#     url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf"
# )


asyncio.run(
    knowledge.add_content_async(
        name="Recipes",
        url="https://agno-public.s3.amazonaws.com/recipes/ThaiRecipes.pdf",
        metadata={"user_tag": "Recipes from website"},
    )
)

# Create agent with knowledge
agent = Agent(
    name="Knowledge Agent",
    knowledge=knowledge,
    search_knowledge=True,
)

agent.print_response("What can you tell me about Thai recipes?")