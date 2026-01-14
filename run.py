import perplexity

# Criar cliente
client = perplexity.Client()

# Fazer uma pergunta
response = client.search("Explain quantum computing", mode="pro", model="claude-4.5-sonnet", sources=["web"])
print(response)
# Mostrar resposta
print("Resposta:", response["answer"])
