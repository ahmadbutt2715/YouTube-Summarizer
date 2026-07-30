from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional



import os
import getpass
from yt_dlp import YoutubeDL
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter





load_dotenv() 

if not os.environ.get("GOOGLE_API_KEY"):
  os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")



# TRANSCRIPT LOADER API
yt_api = YouTubeTranscriptApi()


# TEXT SPLITTER
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# EMBEDDING MODEL
embedding_model = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview"
)


# VECTOR STORE
vector_store = Chroma(
    collection_name="yt_videos_transcripts",
    embedding_function=embedding_model,
    persist_directory="yt_summarizer_chroma_db",
)


# RETRIVER
retriver = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4}
)


# PROMPT
prompt = PromptTemplate(
    template="""
        You are a helpful AI assistant.

        Rules:
        - Answer ONLY from the provided context.
        - If the context is insufficient, just say I dont't know.
        - Respond in plain text only.
        - Do NOT use Markdown.
        - Write naturally, as if you're chatting with a user.
        - Keep the answer concise.
        - - Never refer to the information as "the context." Instead, say "the video," "according to the video," or "based on the video" when appropriate.

        History: {history}
        Context: {context}
        Question: {question}
    """,
    input_variables=['context', 'question', 'history'],
    validate_template = True,
)


# GENERAIVE MODEL (LLM)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    max_tokens=300,
)










# NOTE: session storage (signed cookies) can only hold JSON-safe data.
# If your real pipeline needs to cache a heavy object (vectorstore, retriever,
# LLM chain) per video, keep it here in memory instead of in the session:
_VIDEO_CACHE: dict[str, dict] = {}







class VideoContent(BaseModel):
    video_id: str
    title: str
    summary: str


def extract_video_id(url: str) -> Optional[str]:
    """Pull the 11-char YouTube video id out of common URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None



def get_summary(transcript: str) -> str:
    summarizer_llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    max_tokens=100
    )

    prompt = f"""
    You are a YouTube video summarizer.

    Summarize the following YouTube video transcript in 2-3 concise lines.
    Focus only on the main ideas and avoid unnecessary details.

    Rules:
    - Do NOT write any introduction.
    - Do NOT write "Here is the summary", "Summary:", or similar phrases.
    - Do NOT use bullet points.
    - Output only the summary text.
    - Focus only on the main ideas.

    Transcript:
    {transcript}
    """

    response = summarizer_llm.invoke(prompt)
    return response.text



def get_context(question):
    # retriving
    context_docs = retriver.invoke(question)
    context = '\n\n'.join(text.page_content for text in context_docs)
    return context





def load_video(video_url: str): 
    # Get video id
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("Couldn't find a valid YouTube video id in that URL.")


    # Get title
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

        title = info["title"]

    except Exception as e:
        raise ValueError(f"Failed to fetch title: {type(e).__name__}")


    # Get transcript
    yt_api = YouTubeTranscriptApi()
    try:
        meta_transcript = yt_api.fetch( video_id=video_id, languages=["en"] )
        transcript = ' '.join( data.text for data in meta_transcript.snippets  )
        summary = get_summary( transcript )

    except Exception as e:
        raise ValueError(f"Failed to load: {type(e).__name__}")

    else:
        # splitting
        chunks = splitter.create_documents(
            texts=[transcript],
            metadatas=[{"source": "youtube", 'video_id': video_id}]
        )

        # storing
        vector_store.add_documents(chunks)

        return VideoContent(
            video_id = video_id,
            title = title,
            summary = summary
        )



def ask_question(question: str, history: list[dict]) -> str:
    # get context
    context = get_context(question)

    # prompting
    final_prompt = prompt.invoke( {'history': history, 'context': context, 'question': question} )

    # generation
    answer = llm.invoke(final_prompt)


    return answer.text