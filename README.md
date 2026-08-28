# Sistem za preporuku kozmetičkih proizvoda

## Instalacija

```powershell
python -m pip install -r src/requirements.txt
```

## Pokretanje FastAPI servisa

Pokrenuti iz /src sa:

```powershell
uvicorn backend:app --port 8001
```

## API rute

```text
GET  /                                  osnovna provera dostupnosti
GET  /health                            stanje modela, indeksa i mapiranja
GET  /catalog                           dostupni brendovi i kategorije
POST /recommend                         query-to-product preporuke
GET  /products/similar/{product_id}     item-to-item preporuke
```
