import os
import gradio as gr
import networkx as nx
import json
import logging
import plotly.graph_objects as go
from cbning.llm import process_user_input, interpret_cbn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

initial_cbn = {
    "nodes": [
        {"name": "Clean Water Access", "states": ["Low", "High"], "observable": True},
        {"name": "Community Health", "states": ["Poor", "Good"], "observable": True},
    ],
    "edges": [{"from": "Clean Water Access", "to": "Community Health"}],
    "cpds": {
        "Clean Water Access": {"parents": [], "probabilities": {"": [0.5, 0.5]}},
        "Community Health": {
            "parents": ["Clean Water Access"],
            "probabilities": {"Low": [0.7, 0.3], "High": [0.3, 0.7]},
        },
    },
}


def visualize_cbn(cbn):
    G = nx.DiGraph()

    for node in cbn["nodes"]:
        G.add_node(node["name"], **node)

    for edge in cbn["edges"]:
        G.add_edge(edge["from"], edge["to"])

    pos = nx.spring_layout(G, k=1, iterations=50)

    edge_trace = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            line=dict(width=1, color="#888"),
            hoverinfo='none',
            mode='lines',
            showlegend=False
        ))

    node_trace = go.Scatter(
        x=[pos[node][0] for node in G.nodes()],
        y=[pos[node][1] for node in G.nodes()],
        mode='markers+text',
        hoverinfo='text',
        text=[node for node in G.nodes()],
        textposition="top center",
        marker=dict(
            size=30,
            color='lightblue',
            line=dict(width=2, color='DarkSlateGrey')
        ),
        showlegend=False
    )

    annotations = []
    for node in G.nodes():
        x, y = pos[node]
        node_info = f"{node}<br>States: {', '.join(G.nodes[node]['states'])}"
        cpd_info = f"CPD: {cbn['cpds'][node]['probabilities']}"
        annotations.append(dict(
            x=x, y=y-0.1,
            xref='x', yref='y',
            text=node_info + '<br>' + cpd_info,
            showarrow=False,
            font=dict(size=10),
            align='center',
            bgcolor='white',
            opacity=0.8
        ))

    fig = go.Figure(data=edge_trace + [node_trace],
                    layout=go.Layout(
                        showlegend=False,
                        hovermode='closest',
                        margin=dict(b=5, l=5, r=5, t=35),
                        annotations=annotations,
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    ))

    fig.update_layout(
        autosize=True,
        title={
            'text': "Causal Bayesian Network",
            'y':0.98,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        }
    )

    # Adjust the axis ranges to fit the content
    x_range = max(abs(min(pos[node][0] for node in G.nodes())), abs(max(pos[node][0] for node in G.nodes())))
    y_range = max(abs(min(pos[node][1] for node in G.nodes())), abs(max(pos[node][1] for node in G.nodes())))
    max_range = max(x_range, y_range) * 1.2

    fig.update_xaxes(range=[-max_range, max_range], constrain="domain")
    fig.update_yaxes(range=[-max_range, max_range], constrain="domain", scaleanchor="x", scaleratio=1)

    return fig


def format_json(cbn):
    return json.dumps(cbn, indent=2)


def chatbot_interface(user_input, state, chat_history, chatbot):
    if chat_history is None:
        chat_history = []

    if not chat_history:
        initial_message = """Welcome to the Causal Bayesian Network Builder!

We're starting with a simple scenario:
"Increased access to clean water improves community health outcomes."

You can build upon this by adding more factors, relationships, or refining the existing ones. For example, you might consider adding nodes for:
• Education Programs
• Government Funding
• Infrastructure Development

Feel free to explore and expand the network based on your own ideas and hypotheses! What would you like to add or modify?"""

        ai_message = f"<div style='background-color: #f0f0f0; padding: 10px; border-radius: 5px;'>{initial_message}</div>"
        chat_history.append((None, ai_message))
        logger.info("Initialized chat with welcome message")

        state = initial_cbn.copy()
        fig = visualize_cbn(state)
        initial_interpretation = interpret_cbn(state)

        return (
            state,
            fig,
            chat_history,
            chatbot + [(None, ai_message)],
            "",
            initial_interpretation,
        )

    logger.info(f"Processing user input: {user_input}")
    if state is None:
        state = initial_cbn.copy()
        logger.info("Initializing new CBN state")

    try:
        updated_cbn, suggestions, prompts, subclaims = process_user_input(
            state, user_input
        )
        logger.info("Successfully processed user input")
        fig = visualize_cbn(updated_cbn)

        message = "Based on your input, I've updated the CBN and have the following feedback:\n\n\n"
        message += "Suggestions:\n"
        for suggestion in suggestions:
            message += f"• {suggestion}\n"
        message += "\nPrompts:\n"
        for prompt in prompts:
            message += f"• {prompt}\n"
        message += "\nSubclaims:\n"
        for subclaim in subclaims:
            message += f"• {subclaim}\n"

        user_message = f"<div style='background-color: #e6f3ff; padding: 10px; border-radius: 5px; font-size: 16px;'>{user_input}</div>"
        ai_message = f"<div style='background-color: #f0f0f0; padding: 15px; border-radius: 5px; font-size: 16px;'>{message}</div>"
        chat_history.append((user_message, ai_message))
        logger.info(
            f"CBN updated. Nodes: {len(updated_cbn['nodes'])}, Edges: {len(updated_cbn['edges'])}"
        )
    except Exception as e:
        logger.error(f"Error processing user input: {str(e)}", exc_info=True)
        user_message = f"<div style='background-color: #e6f3ff; padding: 10px; border-radius: 5px; font-size: 16px;'>{user_input}</div>"
        ai_message = f"<div style='background-color: #ffcccc; padding: 15px; border-radius: 5px; font-size: 16px;'>An error occurred while processing your input: {str(e)}</div>"
        chat_history.append((user_message, ai_message))
        updated_cbn = state
        fig = visualize_cbn(updated_cbn)

    interpretation = interpret_cbn(updated_cbn)

    return (
        updated_cbn,
        fig,
        chat_history,
        chatbot + [(user_message, ai_message)],
        "",
        interpretation,
    )


def create_demo():
    logger.info("Creating Gradio demo")
    with gr.Blocks(css="""
        .plot-container { width: 100% !important; height: 800px !important; }
    """) as demo:
        gr.Markdown("# Causal Bayesian Network Builder")

        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(height=800)
                user_input = gr.Textbox(show_label=False, placeholder="Enter your message here...")
            
            with gr.Column(scale=1):
                graph_output = gr.Plot(label="CBN Visualization", elem_classes="plot-container")
                interpretation = gr.Textbox(
                    label="CBN Interpretation",
                    interactive=False,
                    elem_classes="custom-interpretation",
                )

        state = gr.State(initial_cbn)
        chat_history = gr.State([])

        demo.load(
            chatbot_interface,
            [user_input, state, chat_history, chatbot],
            [state, graph_output, chat_history, chatbot, user_input, interpretation],
        )
        user_input.submit(
            chatbot_interface,
            [user_input, state, chat_history, chatbot],
            [state, graph_output, chat_history, chatbot, user_input, interpretation],
        )

    logger.info("Gradio demo created successfully")
    return demo


demo = create_demo()
if __name__ == "__main__":
    debug = os.getenv("DEBUG", "false").lower() == "true"
    share = os.getenv("SHARE", "false").lower() == "true"
    logger.info(f"Launching demo with debug={debug}, share={share}")
    demo.launch(
        debug=debug,
        share=share,
        server_name="0.0.0.0",
        ssl_keyfile=None,
        ssl_certfile=None,
    )