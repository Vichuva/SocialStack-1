from socialstack.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("socialstack.main:app", host="0.0.0.0", port=8000, reload=True)
