import sys
import os
# メインモジュールへのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cost_estimator_agent.cost_estimator_agent import AWSCostEstimatorAgent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """バッチ処理でコスト見積もりを実行"""
    user_input = payload.get("prompt")
    agent = AWSCostEstimatorAgent()

    # バッチ処理
    return agent.estimate_costs(user_input)


if __name__ == "__main__":
    app.run()
