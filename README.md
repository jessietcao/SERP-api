## Running locally
```
source venv/bin/activate

pip install -r requirements.txt

uvicorn main:app --reload
```
## Running in Docker

May take some time to build:
```
docker build -t serp-api .

docker run -p 8000:8000 serp-api
```

## Example queries

### DuckDuckGo
`http://127.0.0.1:8000/search?q=ai+tools&engine=duckduckgo&limit=5`
### Brave
`http://127.0.0.1:8000/search?q=ai+tools&engine=brave&limit=5`
### Bing
`http://127.0.0.1:8000/search?q=ai+tools&engine=bing&limit=5`
### Baidu
`http://127.0.0.1:8000/search?q=ai+tools&engine=baidu&limit=5`
### Google (under construction)
`http://127.0.0.1:8000/search?q=ai+tools&engine=google&limit=5`
