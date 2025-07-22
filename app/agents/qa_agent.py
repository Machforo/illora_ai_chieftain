# importing essential libraries
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from app.services.vector_store import create_vector_store
from app.config import Config
from app.logger import setup_logger

# setting up the logger
logger = setup_logger("QAAgent")

class ConciergeBot:
    def __init__(self):
        try:
            # calling vector embeddings Querying through FAISS
            vector_store = create_vector_store()
            
            # using groq api
            self.llm = ChatOpenAI(
                openai_api_key=Config.GROQ_API_KEY,
                model_name=Config.MODEL_NAME,
                base_url=Config.GROQ_API_BASE,
                temperature=0,
            )

            # Retrieval QA: Connect retriever (FAISS) with LLM
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=vector_store.as_retriever()
            )

            logger.info("LUXORIA SUITES QA agent initialized successfully using Groq.")

        except Exception as e:
            logger.error(f"Error initializing LUXORIA SUITES QA agent: {e}")
            raise

    def ask(self, query: str) -> str:
        try:
            # Custom prompt context to steer LLM for hotel branding
# Custom prompt context to steer LLM for hotel branding
            luxoria_context = (
                "You are a knowledgeable, polite, and concise concierge assistant at *LUXORIA SUITES*, "
                "a premium hotel known for elegant accommodations, gourmet dining, rejuvenating spa treatments, "
                "fully-equipped gym, pool access, 24x7 room service, meeting spaces, and personalized hospitality. "
                "Always provide responses that are short, informative, and relevant to the LUXORIA SUITES experience. "
                "Avoid generic replies — tailor your responses to reflect the hotel’s luxury and exclusivity. "
                "Only elaborate when the guest explicitly asks for more details.\n\n"
                f"Guest Query: {query}"
            )


            response = self.qa_chain.run(luxoria_context)
            logger.info(f"Processed query at LUXORIA SUITES: {query}")
            return response

        except Exception as e:
            logger.error(f"Error processing query at LUXORIA SUITES '{query}': {e}")
            return (
                "We're sorry, there was an issue while assisting you. "
                "Please feel free to ask again or contact the LUXORIA SUITES front desk for immediate help."
            )
