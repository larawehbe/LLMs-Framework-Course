from typing_extensions import TypedDict, Literal
from IPython.display import Image, display
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()


llm = ChatOpenAI(model='gpt-4o-mini')


class JokeState(TypedDict):
    topic: str
    joke: str
    improved_joke: str
    final_joke: str

def generate_joke(state :JokeState):
    topic = state['topic']

    prompt = f"Generate a joke based on this topic: {topic}"
    response = llm.invoke(prompt)
    return {"joke" : response.content}

def improve_joke(state: JokeState):
    joke = state['joke']
    prompt = f"Improve this joke by making it meaningful: {joke}"
    response = llm.invoke(prompt)
    return {"improved_joke" : response.content}

def final_joke(state: JokeState):
    improve_joke =state['improved_joke']
    prompt = f'Make this joke about schools {improve_joke}'
    response = llm.invoke(prompt)
    return {"final_joke" : response.content}


def is_valid(state : JokeState) -> Literal["improve_joke_node" , END]:
    
    joke = state['joke']
    print(len(joke) <= 10 )
    return "improve_joke_node" if len(joke) <= 10 else END



agent = StateGraph(JokeState)

agent.add_node("generate_joke_node" , generate_joke)
agent.add_node("improve_joke_node" , improve_joke)
agent.add_node("final_joke_node" , final_joke)

agent.add_edge(START, "generate_joke_node")
agent.add_conditional_edges(
    "generate_joke_node" , 
    is_valid ,
    ['improve_joke_node' , END]
)
agent.add_edge("improve_joke_node" , "final_joke_node")
agent.add_edge("final_joke_node", END)

workflow = agent.compile()

joke_state = {
    "topic" : "ai robots",
    "joke" : "",
    "improved_joke" : "",
    "final_joke" : ""
}

response = workflow.invoke(joke_state)

print(response)


print("--------")
print(f"\t ---> Topic : {response['topic']}" )
print(f"\t ---> Joke: {response['joke']}" )
if response['improved_joke'] :
    print(f"\t --->  Improved joke: {response['improved_joke']}" )
    print(f"\t --->  Final Joke: {response['final_joke']}" )
else:
    print(f"\t ---> Joke is Invalid!" )