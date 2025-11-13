import google.generativeai as genai

genai.configure(api_key="AIzaSyDWIke_yHhzUW2P6kJPCjd5YOpf_RnMDOQ")

models = genai.list_models()
for m in models:
    print(m.name)
