"""Knowledge base management for Handler server agent.

Provides Qdrant-backed semantic search for A2A protocol expertise using
the Qdrant MCP server for tool integration with Google ADK.
"""

import os
from pathlib import Path

from a2a_handler.common import get_logger

logger = get_logger(__name__)

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "a2a-knowledge"
QDRANT_COLLECTION = "a2a_knowledge"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def get_knowledge_files() -> list[Path]:
    """Get all markdown files from the knowledge base directory.

    Returns:
        List of paths to knowledge base files
    """
    if not ASSETS_DIR.exists():
        logger.warning("Knowledge base directory not found: %s", ASSETS_DIR)
        return []

    files = list(ASSETS_DIR.glob("*.md"))
    logger.info("Found %d knowledge base files", len(files))
    return files


def chunk_document(
    content: str, chunk_size: int = 1000, overlap: int = 200
) -> list[str]:
    """Split a document into overlapping chunks for embedding.

    Args:
        content: The document content to chunk
        chunk_size: Target size of each chunk in characters
        overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunks
    """
    chunks = []
    lines = content.split("\n")
    current_chunk = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1
        if current_size + line_size > chunk_size and current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunks.append(chunk_text)

            overlap_text = (
                chunk_text[-overlap:] if len(chunk_text) > overlap else chunk_text
            )
            overlap_lines = overlap_text.split("\n")
            current_chunk = overlap_lines
            current_size = len(overlap_text)

        current_chunk.append(line)
        current_size += line_size

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def get_qdrant_local_path() -> str:
    """Get the path for local Qdrant storage.

    Returns:
        Path string for Qdrant local storage
    """
    data_dir = Path.home() / ".handler" / "qdrant"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


def get_mcp_server_env() -> dict[str, str]:
    """Get environment variables for the Qdrant MCP server.

    Returns:
        Dictionary of environment variables
    """
    return {
        "QDRANT_LOCAL_PATH": get_qdrant_local_path(),
        "COLLECTION_NAME": QDRANT_COLLECTION,
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        "EMBEDDING_PROVIDER": "fastembed",
        "TOOL_STORE_DESCRIPTION": (
            "Store information about the A2A protocol, Handler application, "
            "or related knowledge. Use this to remember important facts, "
            "code examples, and protocol details."
        ),
        "TOOL_FIND_DESCRIPTION": (
            "Search the A2A protocol knowledge base for relevant information. "
            "Use this to find details about A2A concepts, Handler usage, "
            "protocol methods, data structures, and best practices."
        ),
    }


async def initialize_knowledge_base() -> bool:
    """Initialize the knowledge base by loading documents into Qdrant.

    This function reads all markdown files from the knowledge base directory
    and indexes them into Qdrant for semantic search.

    Returns:
        True if initialization was successful, False otherwise
    """
    try:
        from qdrant_client import QdrantClient

        qdrant_path = get_qdrant_local_path()
        logger.info("Initializing Qdrant at: %s", qdrant_path)

        client = QdrantClient(path=qdrant_path)

        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if QDRANT_COLLECTION in collection_names:
            collection_info = client.get_collection(QDRANT_COLLECTION)
            if collection_info.points_count > 0:
                logger.info(
                    "Knowledge base already initialized with %d points",
                    collection_info.points_count,
                )
                return True

        knowledge_files = get_knowledge_files()
        if not knowledge_files:
            logger.warning("No knowledge files found to index")
            return False

        all_chunks = []
        all_metadata = []

        for file_path in knowledge_files:
            logger.info("Processing: %s", file_path.name)
            content = file_path.read_text()
            chunks = chunk_document(content)

            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadata.append(
                    {
                        "source": file_path.name,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                    }
                )

        logger.info("Indexing %d chunks into Qdrant...", len(all_chunks))

        client.add(
            collection_name=QDRANT_COLLECTION,
            documents=all_chunks,
            metadata=all_metadata,
        )

        logger.info("Knowledge base initialized successfully")
        return True

    except ImportError:
        logger.error(
            "qdrant-client not installed. Run: pip install qdrant-client[fastembed]"
        )
        return False
    except Exception as e:
        logger.error("Failed to initialize knowledge base: %s", e)
        return False
