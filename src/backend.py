# backend.py
from fastapi import FastAPI, HTTPException
from pathlib import Path
from pydantic import BaseModel, Field
import faiss
from sentence_transformers import SentenceTransformer
from contextlib import asynccontextmanager
import pandas as pd
import html
import unicodedata
import re
import numpy as np

data_path=Path(__file__).resolve().parents[1] / 'data'
DEVICE = 'cpu' 
GTE_MODEL_ID = 'Alibaba-NLP/gte-multilingual-base'
GTE_REVISION = '9bbca17d9273fd0d03d5725c7a4b0f6b45142062'
DEPTH=5

class RecommendResponse(BaseModel):
    logical_product_id: str
    product_name: str
    brand: str
    category: str
    price: float
    page_rating: float | None =None
    description: str 
    rank: int

class Catalog(BaseModel):
    brands: list[str] 
    categories: list[str] 
    max_price: float

class RecommendRequest(BaseModel):
    query: str = Field(min_length=1)
    brand: str | None = None
    category: str | None = None
    max_price: int | None = Field(default=None)


def clean_query_text(value : str):
    if not value:
        return None 
    text = html.unescape(str(value))
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()

def faiss_search(embedding : np.ndarray, allowed_products : pd.DataFrame) -> list[RecommendResponse] :
    distances, idx = gte_index.search(embedding,gte_index.ntotal)
    ranked = pd.DataFrame({
        "logical_product_id": (mapping.iloc[ idx[0] ]["logical_product_id"].values),
        "score": distances[0]})
    ranked = ranked.merge(allowed_products,on="logical_product_id",how="inner",validate="one_to_one").head(DEPTH)
    ranked.insert(0,"rank",np.arange(1, len(ranked) + 1))
    columns=['logical_product_id', 'product_name', 'brand', 'category', 'price', 'page_rating', 'description', 'rank']
    ranked=ranked[columns].to_dict(orient='records')
    return [RecommendResponse(**row) for row in ranked]


def find_recommendations(request: RecommendRequest) -> list[RecommendResponse] : 
    query_clean=clean_query_text(request.query)
    ####### ovo bih mozda i propustila al sa
    if not query_clean:
        raise HTTPException(status_code = 400, detail = "Query can't be empty")
    gte_query_embedding = gte_model.encode(query_clean,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
    gte_query_embedding = np.ascontiguousarray(gte_query_embedding.reshape(1,-1),dtype=np.float32)
    allowed_products= products.copy()

    if request.brand is not None and request.brand.strip():
        allowed_products=allowed_products[allowed_products.brand.eq(request.brand.strip())] 
    if request.category is not None and request.category.strip():
        allowed_products=allowed_products[allowed_products.category.eq(request.category.strip())] 
    #ne primenjuje filter ako nije uneta cena ili je 0
    if request.max_price is not None and request.max_price>0:
        allowed_products=allowed_products[allowed_products.price.le(request.max_price)]
    return faiss_search(gte_query_embedding, allowed_products)


def find_similar(product_id: str)->list[RecommendResponse]:
    if not product_id:
        raise HTTPException(status_code = 400, detail = "Product_id can't be empty")
    product_id=product_id.strip()
    requested_mapping = mapping[mapping.logical_product_id==product_id]
    requested_product = products[products.logical_product_id==product_id]
    if len(requested_mapping)==0 or len(requested_product)==0:
        raise HTTPException(status_code = 404, detail = f"No products found with {product_id} product_id")
    faiss_row = int(requested_mapping.iloc[0]["faiss_row"])    
    requested_category = requested_product.category.values[0]

    gte_product_embedding=gte_index.reconstruct(faiss_row)
    gte_product_embedding = np.ascontiguousarray(gte_product_embedding.reshape(1,-1),dtype=np.float32)
    mask=(products.category.eq(requested_category)) & (products.logical_product_id.ne(product_id))
    allowed_products= products[mask].copy()
    return faiss_search(gte_product_embedding, allowed_products)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global products,mapping, gte_index, gte_model
    products = pd.read_csv(data_path / 'processed' / 'products_logical.csv')
    products['price']  = pd.to_numeric(products.price, errors= 'coerce')
    products['page_rating']  = pd.to_numeric(products.page_rating, errors= 'coerce')
    products["page_rating"] = products["page_rating"].astype(object).where(products["page_rating"].notna(), None)
    mapping = pd.read_csv(data_path / 'indexes' / 'gte' / 'product_rows.csv')
    gte_index =faiss.read_index( str(data_path / 'indexes' / 'gte' / 'products.faiss'))
    gte_model = SentenceTransformer(GTE_MODEL_ID,revision=GTE_REVISION,trust_remote_code=True,device=DEVICE)
    yield

app=FastAPI(title='Cosmetics Recommender', lifespan=lifespan)

@app.get("/")
def read_root():
    return {"Hello": "User"}

@app.post("/recommend", response_model=list[RecommendResponse])
def recommend_search(request: RecommendRequest) ->list[RecommendResponse] :
    return find_recommendations(request)


@app.get("/catalog", response_model=Catalog)
def get_catalog() -> Catalog:
    brands=products.brand.unique().tolist()
    categories=products.category.unique().tolist()
    price=products.price.max()
    return Catalog(brands = sorted(brands), categories = sorted(categories), max_price=price)


@app.get("/products/similar/{product_id}", response_model=list[RecommendResponse])
def find_similar_item(product_id: str)->list[RecommendResponse]:  # Type hint 'int' ensures automatic data parsing
    return find_similar(product_id)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": gte_model is not None, "index_loaded": gte_index is not None,"mapping_loaded": mapping is not None}
