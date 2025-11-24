from exa_py import Exa
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

exa = Exa(api_key = os.getenv("EXA_API_KEY"))

# def research_exa(user_query):
#     research = exa.research.create(
#       instructions = user_query,
#       model = "exa-research-fast",
#       output_schema = {
#         "type": "object",
#         "required": ["taxonomy", "averageLifespan", "notableBehaviors"],
#         "properties": {
#           "taxonomy": {
#             "type": "object",
#             "required": ["kingdom", "phylum", "class", "order", "family", "genus", "species"],
#             "properties": {
#               "kingdom": {
#                 "type": "string"
#               },
#               "phylum": {
#                 "type": "string"
#               },
#               "class": {
#                 "type": "string"
#               },
#               "order": {
#                 "type": "string"
#               },
#               "family": {
#                 "type": "string"
#               },
#               "genus": {
#                 "type": "string"
#               },
#               "species": {
#                 "type": "string"
#               }
#             }
#           },
#           "averageLifespan": {
#             "type": "object",
#             "properties": {
#               "worker": {
#                 "type": "string",
#                 "description": "Typical lifespan of worker ants"
#               },
#               "queen": {
#                 "type": "string",
#                 "description": "Typical lifespan of queen ants"
#               }
#             }
#           },
#           "notableBehaviors": {
#             "type": "array",
#             "items": {
#               "type": "string"
#             }
#           }
#         },
#         "additionalProperties": false
#       },
      
#     )
#     for event in exa.research.get(research.research_id, stream = True):
#         print(event)

#     # Research can also be used (without an output schema)
#     # directly inside chat completions

#     client = OpenAI(
#         base_url = "https://api.exa.ai",
#         api_key = "EXA_API_KEY",
#     )

#     completion = client.chat.completions.create(
#         model = "exa-research-fast",
#         messages = [
#             {"role": "user", "content": "Provide scientific information about ants including taxonomy, average lifespan, and notable behaviors"}
#         ],
#         stream = True,
#     )

#     for chunk in completion:
#         if chunk.choices and chunk.choices[0].delta.content:
#             print(chunk.choices[0].delta.content, end = "", flush = True)
        

'''Use the answer api whichever is needed'''
def query_exa(user_query):
    client = OpenAI(
      base_url = "https://api.exa.ai",
      api_key = os.getenv("EXA_API_KEY"),
    )

    completion = client.chat.completions.create(
      model = "exa",
      messages = [{"role":"user","content":user_query}],
    )
    
    return completion