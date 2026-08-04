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
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough


load_dotenv() 

if not os.environ.get("GOOGLE_API_KEY"):
  os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter API key for Google Gemini: ")






# TEXT SPLITTER
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# EMBEDDING MODEL
embedding_model = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview"
)


# VECTOR STORE
# every thing is stored in RAM
vector_store = Chroma(
    collection_name="yt_videos_transcripts",
    embedding_function=embedding_model,
)


# RETRIVER
retriver = vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={"k": 4}
)


# GENERAIVE MODEL (LLM)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    max_tokens=300,
)


# QUESTION PROMPT
question_prompt = PromptTemplate(
    template="""
        You are a helpful AI assistant.

        Rules:
        - Answer ONLY from the provided context.
        - If the context is insufficient, tell the user that this topic/question is not in video.
        - Respond in plain text only.
        - Do NOT use Markdown.
        - Write naturally, as if you're chatting with a user.
        - Keep the answer concise.
        - - Never refer to the information as "the context."

        Context: {context}
        Question: {question}
    """,
    input_variables=['context', 'question'],
)


# SUMMARY PROMPT 
summary_prompt = PromptTemplate(
    template="""
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
    """,
    input_variables=['transcript'],
)


# PARSER
output_parser = StrOutputParser()





# HELPER FUNCTIONS

class VideoContent(BaseModel):
    video_id: str
    title: str
    summary: str



def extract_video_id(url: str) -> str:
    """Pull the 11-char YouTube video id out of common URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    video_id = None
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        raise ValueError("Couldn't find a valid YouTube video id in that URL.")

    return video_id



def get_title(video_id):
    """Get title of video"""
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

        title = info["title"]

    except Exception as e:
        raise ValueError(f"Failed to fetch title: {type(e).__name__}: {e}")

    return title



def get_transcript(video_id):
    """Get transcript of video"""
    yt_api = YouTubeTranscriptApi()
    try:
        meta_transcript = yt_api.fetch( video_id=video_id, languages=["en"] )
        transcript = ' '.join( data.text for data in meta_transcript.snippets  )

    except Exception as e:
        raise ValueError(f"Failed to load transcript: {type(e).__name__}: {e}")

    return transcript



def store_transcript(data: dict) -> str:
    """data = {'title':..., 'transcript':...} — splits + stores into Chroma."""
    """Wipe whatever was stored before, then store this video's transcript only."""
    existing = vector_store.get()
    if existing["ids"]:
        vector_store.delete(ids=existing["ids"])

    docs = splitter.create_documents(
        [data["transcript"]],
        metadatas=[{"title": data["title"]}],
    )
    vector_store.add_documents(docs)
    return "stored"


def formate_docs(retrived_docs):
    if not retrived_docs:
        return "No relevant content found."
    
    title = retrived_docs[0].metadata.get("title", "")
    context = '\n\n'.join(doc.page_content for doc in retrived_docs)

    print( f"VideoTitle: {title}\n\nContext: {context}" )    # print on server
    return f"VideoTitle: {title}\n\nContext: {context}"











# MAIN FUNCTIONS 

def load_video(video_url: str): 

    video_id = extract_video_id(video_url)
    title = get_title(video_id)
    transcript = get_transcript(video_id) 

    summary_chain = summary_prompt | llm | output_parser
    summary = summary_chain.invoke({'transcript': transcript})


    store_transcript({'transcript': transcript, 'title': title})


    return VideoContent(
        video_id=video_id,
        title=title,
        summary=summary,
    )



def ask_question(question: str) -> str:

    parallel_chain = RunnableParallel(
        {
            'context': retriver | RunnableLambda(formate_docs),
            'question': RunnablePassthrough()
        }
    )

    main_chain =  parallel_chain |  question_prompt | llm | output_parser


    # invoke chain
    result =  main_chain.invoke( question )

    print(retriver.invoke(question))  # print on server


    return result