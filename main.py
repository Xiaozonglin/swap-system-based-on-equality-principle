from flask import Flask, render_template, request, redirect
import tldextract
from urllib.parse import urlparse

app = Flask(__name__)

db = None
cursor = None

try:
    import pymysql
    db = pymysql.connect(
        host='localhost',
        user='root',
        password='root',
        database='transfer',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = db.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `links` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `domain1` VARCHAR(100) NOT NULL,
            `domain2` VARCHAR(100) NOT NULL,
            `one2two` INT NOT NULL DEFAULT 0,
            `two2one` INT NOT NULL DEFAULT 0,
            UNIQUE KEY `domain_pair` (`domain1`, `domain2`)
        ) ENGINE = InnoDB DEFAULT CHARSET=utf8mb4
    """)
    db.commit()
    
except Exception as e:
    print(f"数据库初始化失败: {e}")
    if db:
        db.close()
    exit(1)

def validate_url(url):
    """验证URL格式"""
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

def get_domain_from_url(url):
    """从URL中提取域名"""
    if not validate_url(url):
        return None
    extracted = tldextract.extract(url)
    if not extracted.domain or not extracted.suffix:
        return None
    return f"{extracted.domain}.{extracted.suffix}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/go')
def go():
    from_url = request.args.get('from', '').strip()
    to_url = request.args.get('to', '').strip()
    
    if not from_url or not to_url:
        return "链接双方未指定", 400
    
    if len(from_url) > 500 or len(to_url) > 500:
        return "参数过长", 400
    
    if not validate_url(from_url) or not validate_url(to_url):
        return "URL格式无效", 400
    
    from_domain = get_domain_from_url(from_url)
    to_domain = get_domain_from_url(to_url)
    
    if not from_domain or not to_domain:
        return "无法提取有效域名", 400
    
    referer = request.headers.get('Referer')
    if referer:
        referer_domain = get_domain_from_url(referer)
        if referer_domain and referer_domain != from_domain:
            return "来源页面与提供的源页面不匹配", 400
    
    try:
        # 查询正向跳转记录
        cursor.execute(
            "SELECT * FROM links WHERE domain1 = %s AND domain2 = %s",
            (from_domain, to_domain)
        )
        result = cursor.fetchone()
        
        if result:
            one2two = result['one2two']
            two2one = result['two2one']
            
            # 判断是否需要返回
            if one2two > two2one * 1.2 and one2two > 5:
                return render_template('return.html', backurl=from_url)
            else:
                # 更新正向计数
                cursor.execute(
                    "UPDATE links SET one2two = one2two + 1 WHERE domain1 = %s AND domain2 = %s",
                    (from_domain, to_domain)
                )
                db.commit()
                return redirect(to_url)
        else:
            # 查询反向跳转记录
            cursor.execute(
                "SELECT * FROM links WHERE domain1 = %s AND domain2 = %s",
                (to_domain, from_domain)
            )
            result = cursor.fetchone()
            
            if result:
                one2two = result['one2two']
                two2one = result['two2one']
                
                # 注意：这里逻辑与上面相反，因为方向反了
                if two2one > one2two * 1.2 and two2one > 5:
                    return render_template('return.html', backurl=from_url)
                else:
                    # 更新反向计数
                    cursor.execute(
                        "UPDATE links SET two2one = two2one + 1 WHERE domain1 = %s AND domain2 = %s",
                        (to_domain, from_domain)
                    )
                    db.commit()
                    return redirect(to_url)
            else:
                # 创建新的跳转对
                cursor.execute(
                    "INSERT INTO links (domain1, domain2, one2two) VALUES (%s, %s, 1)",
                    (from_domain, to_domain)
                )
                db.commit()
                return redirect(to_url)
                
    except Exception as e:
        db.rollback()
        print(f"数据库操作失败: {e}")
        return "系统内部错误", 500

@app.errorhandler(404)
def page_not_found(e):
    return "页面未找到", 404

@app.errorhandler(500)
def internal_server_error(e):
    return "内部服务器错误", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)