from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from dotenv import load_dotenv
from products import PRODUCTS

load_dotenv()

app = FastAPI(
    title="Jasify AI Backend API",
    description="AI-powered marketplace backend for Jasify",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
HF_API_KEY = os.getenv("HF_API_KEY")
HF_MODEL = "deepseek-ai/DeepSeek-V3-0324"
HF_API_URL = "https://router.huggingface.co/v1/chat/completions"


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Jasify AI Backend"}


@app.get("/products")
async def get_products():
    """Get all products in the catalog"""
    return {"products": PRODUCTS, "total": len(PRODUCTS)}


@app.get("/ai-overview")
async def ai_overview(query: str):
    """
    Generate an AI overview for a given query using Hugging Face API
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")

    try:
        prompt = f"""You are an AI assistant for the Jasify AI marketplace. 
A user is searching for: "{query}"

Provide a concise, helpful overview (2-3 sentences) about what they're looking for and how AI tools can help them. 
Be specific and actionable."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HF_API_URL,
                headers={
                    "Authorization": f"Bearer {HF_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": HF_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                    "temperature": 0.7,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Hugging Face API error: {response.text}"
            )

        data = response.json()
        summary = data["choices"][0]["message"]["content"].strip()

        return {"summary": summary, "query": query}

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request to AI service timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating overview: {str(e)}")


@app.get("/recommendations")
async def get_recommendations(query: str):
    """
    Get personalized AI product recommendations based on query
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query parameter is required")

    try:
        # Create a prompt to rank products
        products_text = "\n".join([
            f"- {p['name']} ({p['category']}): {p['description']}"
            for p in PRODUCTS
        ])

        prompt = f"""You are an AI assistant for the Jasify AI marketplace.
A user is looking for: "{query}"

From this list of AI products, select the TOP 3-5 most relevant ones:
{products_text}

Return ONLY the product names, one per line, in order of relevance. No explanations."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HF_API_URL,
                headers={
                    "Authorization": f"Bearer {HF_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": HF_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.5,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Hugging Face API error: {response.text}"
            )

        data = response.json()
        recommended_names = data["choices"][0]["message"]["content"].strip().split("\n")
        recommended_names = [name.strip().strip("-").strip() for name in recommended_names if name.strip()]

        # Match recommended names to products
        recommendations = []
        for name in recommended_names:
            for product in PRODUCTS:
                if name.lower() in product["name"].lower() or product["name"].lower() in name.lower():
                    recommendations.append(product)
                    break

        # If no matches found, return top products from matching categories
        if not recommendations:
            query_lower = query.lower()
            recommendations = [
                p for p in PRODUCTS
                if any(keyword in p["description"].lower() or keyword in p["category"].lower()
                       for keyword in query_lower.split())
            ][:5]

        return {"recommendations": recommendations, "query": query}

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request to AI service timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
