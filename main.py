from fastapi import FastAPI, HTTPException, Request
import redis
from datetime import timedelta
import time

# Initialize FastAPI app
app = FastAPI()

# Initialize Redis connection
redis_client = redis.StrictRedis(host='localhost', port=6379, decode_responses=True)

# Rate limit settings
RATE_LIMIT = 10  # Number of allowed requests
TIME_WINDOW = 60  # Time window in seconds (e.g., 60 seconds = 1 minute)


def rate_limiter(client_id: str):
    """
    Rate limiter using Redis.
    :param client_id: A unique identifier for the client (e.g., IP address or API key).
    :raises: HTTPException if rate limit is exceeded.
    """
    # Create a Redis key for the client
    redis_key = f"rate_limit:{client_id}"
    
    # Get the current count from Redis
    request_count = redis_client.get(redis_key)
    
    if request_count is None:
        # If no count exists, set it with expiration time
        redis_client.set(redis_key, 1, ex=TIME_WINDOW)
    else:
        request_count = int(request_count)
        if request_count >= RATE_LIMIT:
            # If the limit is reached, raise an exception
            retry_after = redis_client.ttl(redis_key)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )
        else:
            # Increment the count
            redis_client.incr(redis_key)


@app.middleware("http")
async def add_rate_limit_header(request: Request, call_next):
    """
    Middleware to add rate limit headers to the response.
    """
    client_id = request.client.host  # Using the client's IP as the identifier
    redis_key = f"rate_limit:{client_id}"
    request_count = redis_client.get(redis_key) or 0
    remaining_requests = max(0, RATE_LIMIT - int(request_count))

    # Process the request
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
    response.headers["X-RateLimit-Reset"] = str(redis_client.ttl(redis_key) or TIME_WINDOW)
    return response


@app.get("/api/protected")
async def protected_endpoint(request: Request):
    """
    A protected endpoint with rate limiting.
    """
    client_id = request.client.host  # Use the client's IP address as the identifier
    rate_limiter(client_id)
    return {"message": "This is a protected API endpoint!"}


@app.get("/api/status")
async def api_status():
    """
    An open endpoint to check API status.
    """
    return {"message": "API is running smoothly!"}



