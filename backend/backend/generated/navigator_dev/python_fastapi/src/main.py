from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from prisma import Prisma
from datetime import datetime

app = FastAPI()
db = Prisma()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

class PostCreate(BaseModel):
    title: str
    content: str

@app.get("/api/posts")
async def get_posts(page: int = Query(1), limit: int = Query(10)):
    posts = await db.posts.find_many(skip=(page-1)*limit, take=limit, order={'created_at': 'desc'})
    total = await db.posts.count()
    return {"data": posts, "meta": {"total": total, "page": page}}

@app.post("/api/posts")
async def create_post(post: PostCreate):
    new_post = await db.posts.create(data={'title': post.title, 'content': post.content})
    return new_post

@app.get("/api/posts/{id}")
async def get_post(id: str):
    post = await db.posts.find_unique(where={'id': id})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post