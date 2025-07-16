from langchain_community.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from app.services.vector_store import create_vector_store
from app.config import Config
from app.logger import setup_logger

logger = setup_logger("QAAgent")

class ConciergeBot:
    def __init__(self):
        try:
            vector_store = create_vector_store()

            self.llm = ChatOpenAI(
                openai_api_key=Config.GROQ_API_KEY,
                model_name=Config.MODEL_NAME,
                base_url=Config.GROQ_API_BASE,
                temperature=0,
            )

            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=vector_store.as_retriever()
            )

            logger.info("Groq-based QA agent initialized successfully.")

        except Exception as e:
            logger.error(f"Error initializing QA agent: {e}")
            raise

    def ask(self, query: str) -> str:
        try:
            response = self.qa_chain.run(query)
            logger.info(f"Processed query: {query}")
            return response
        except Exception as e:
            logger.error(f"Error handling query '{query}': {e}")
            return "Sorry, there was an error processing your request."
