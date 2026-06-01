"""OCR结果相似度比较工具，用于比较两个OCR引擎对同一文档的识别结果并评估相似度"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("api_key"),
    base_url=os.getenv("base_url")
)

def get_similarity_prompt(result1: str, result2: str) -> str:
    prompt = f'''
        你是一位顶级的OCR结果一致性评估专家，你的任务是深入分析和对比两个OCR引擎对同一份文档的识别结果，
        并提供一份全面、精确的评估报告。
        
        ## 评估标准
        
        1. **完全一致 (100%)**: 两个引擎识别结果在语义和关键信息上完全相同
        2. **高度一致 (≥90%)**: 相似度≥90%，仅有微小差异（如标点、空格、个别字符等）
        3. **部分一致 (70-90%)**: 相似度在70-90%之间，关键信息基本一致但存在局部差异
        4. **低度一致 (<70%)**: 相似度<70%，存在显著差异
        
        ## 输入数据
        
        ### OCR结果1:
        {result1}
        
        ### OCR结果2:
        {result2}
        
        根据以上标准和提供的数据，输出的评估结果应仅为以下之一，不需要额外分析：
            完全一致 (100%)
            高度一致 (≥90%)
            部分一致 (70-90%)
            低度一致 (<70%)
        '''
    return prompt

def compare_ocr_results(result1: str, result2: str) -> dict:
    try:
        prompt = get_similarity_prompt(result1, result2)
        messages = [{"role": "user", "content": prompt}]
        completion = client.chat.completions.create(
            model="qwen3-max", 
            messages=messages
        )
        content = completion.choices[0].message.content
        return content
    except Exception as e:
        return None


def get_ocr_results_diff(result1: str, result2: str) -> dict:
    try:
        prompt = f"""
        #role
            你是一个文本内容比对助手，根据用户输入的两段文本，判断两段文本中是否存在内容不同的部分。
        #任务
            1.根据用户输入的两段文本，判断两段文本中是否存在内容不同的部分。2.若没有不同，输出"相同"，若有不同，输出"不同"并输出内容不同的字段
                ## 输入数据
                ### 文本1:
                    {result1}
                ### 文本2:
                    {result2}
        """

        messages = [{"role": "user", "content": prompt}]
        completion = client.chat.completions.create(
            model="qwen3-max",
            messages=messages
        )
        content = completion.choices[0].message.content
        return content
    except Exception as e:
        return None

if __name__ == "__main__":
    analysis = "示例OCR结果1"
    analysis_bak = "示例OCR结果2"
    
    result = compare_ocr_results(analysis, analysis_bak)
    
    if result["status"] == "success":
        print("OCR结果比较完成:")
        print(result["comparison_result"])
    else:
        print(f"比较过程中出现错误: {result['error_message']}")