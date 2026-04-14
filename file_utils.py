# file_utils.py
import tempfile
import os
from typing import Dict, Any, List

from config import logger, PINECONE_API_KEY, PINECONE_INDEX_NAME
from llm_setup import llm, embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter


async def process_uploaded_file(tmp_path: str, filename: str, owner_id: str = "unknown") -> str:
    """
    Processes the uploaded file from disk, extracts text, generates a summary using the LLM,
    and ingests embeddings into Pinecone if configured.
    Uses pymupdf4llm for PDF extraction (consistent with Notebook Oracle path).
    """
    suffix = os.path.splitext(filename)[1].lower() if filename else ".dat"

    text = ""
    try:
        if suffix == ".pdf":
            try:
                import pymupdf4llm
                text = pymupdf4llm.to_markdown(tmp_path)
                logger.info(f"[file_utils] Processed PDF '{filename}' via pymupdf4llm ({len(text)} chars extracted).")
            except Exception as e:
                logger.error(f"[file_utils] PDF extraction failed for '{filename}': {e}")
                text = ""
        else:
            try:
                with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                logger.info(f"[file_utils] Processed text file '{filename}' ({len(text)} chars extracted).")
            except Exception:
                logger.error(f"[file_utils] Error reading text file '{filename}'.")
                text = ""

        indexed = False
        if PINECONE_API_KEY and embeddings and text.strip():
            try:
                from langchain_pinecone import PineconeVectorStore

                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                chunks = text_splitter.split_text(text)
                if not chunks:
                    logger.warning(f"[file_utils] No text chunks extracted from {filename}; skipping Pinecone ingestion.")
                else:
                    metadatas = [{"source": filename, "chunk": i, "owner_id": owner_id, "role": "student"} for i in range(len(chunks))]
                    PineconeVectorStore.from_texts(
                        chunks,
                        embedding=embeddings,
                        index_name=PINECONE_INDEX_NAME,
                        metadatas=metadatas
                    )
                    indexed = True
                    logger.info(f"[file_utils] Ingested {len(chunks)} chunks from {filename} to Pinecone.")
            except Exception as e:
                logger.error(f"[file_utils] Pinecone ingestion failed for {filename}: {e}")

        # Clip text for LLM summary input (~16k chars Γëê ~4k tokens)
        SUMMARY_CLIP_CHARS = 16000
        clipped = text[:SUMMARY_CLIP_CHARS]

        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that summarizes uploaded documents for later use."),
            ("user", "Please produce a concise (max 120 words) summary of this document. "
                     "If the document is meant for a child, note age-appropriate vocabulary:\n\n{document_content}")
        ])
        summary_chain = summary_prompt | llm | StrOutputParser()

        summary = await summary_chain.ainvoke({"document_content": clipped})
        if indexed:
            summary += "\n(Document was also successfully indexed in Vector Database for deep search.)"
        logger.info(f"[file_utils] Generated summary for {filename}: {summary[:50]}...")
        return summary
    except Exception as e:
        logger.error(f"[file_utils] Processing failed for {filename}: {e}")
        raise
