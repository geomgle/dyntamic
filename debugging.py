import uvicorn
from fastapi import FastAPI
from src.dyntamic.old_dyntamic import test

app = FastAPI()


@app.get("/")
async def root():
    res = await test()
    return {"message": res}


if __name__ == "__main__":
    print("Running in debug mode")

    # Run the Uvicorn server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_keep_alive=60 * 60 * 24,
        log_level="critical",
    )
