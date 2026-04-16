import json
import time
from utils.db_utils import connection_pool


# 添加缓存变量和过期时间（秒）
_cpt_cache = None
_cpt_cache_timestamp = 0
_CPT_CACHE_EXPIRY = 86400  # 24小时缓存时间


def get_cpt_data_as_json():
    """
    执行SQL查询并获取CPT数据，然后转换为JSON格式的字符串
    """
    global _cpt_cache, _cpt_cache_timestamp
    
    # 检查缓存是否有效
    current_time = time.time()
    if _cpt_cache is not None and (current_time - _cpt_cache_timestamp) < _CPT_CACHE_EXPIRY:
        print("从缓存中获取CPT数据")
        return _cpt_cache
    
    connection = connection_pool.connection()
    cursor = connection.cursor()

    try:
        query = "SELECT cpt_code, description FROM cpt "
        cursor.execute(query)
        results = cursor.fetchall()

        # 检查是否有结果
        if not results:
            print("警告: CPT表中没有有效数据，返回空数组")
            cache_result = "[]"
        else:
            # 转换为JSON格式的字符串
            cache_result = json.dumps(results, ensure_ascii=False)
            print(f"CPT数据加载完成，共 {len(results)} 条记录")

        # 更新缓存
        _cpt_cache = cache_result
        _cpt_cache_timestamp = current_time
        
        return cache_result
    except Exception as e:
        print(f"获取CPT数据时出错: {e}")
        # 返回空数组的JSON字符串作为默认值
        return "[]"
    finally:
        cursor.close()
        connection.close()