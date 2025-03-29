
from quart import render_template_string
async def base_error_page(title, message):
    return await render_template_string(
        """
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Roboto', sans-serif;
                    background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
                    color: #333;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }
                .container {
                    max-width: 500px;
                    width: 100%;
                    background: #fff;
                    border-radius: 12px;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
                    padding: 30px;
                    text-align: center;
                    animation: fadeIn 0.5s ease;
                }
                h1 {
                    font-size: 24px;
                    color: #e74c3c;
                    margin-bottom: 20px;
                    position: relative;
                    padding-bottom: 10px;
                }
                h1:after {
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 50%;
                    transform: translateX(-50%);
                    width: 50px;
                    height: 3px;
                    background: #e74c3c;
                }
                p {
                    font-size: 16px;
                    color: #555;
                    margin-bottom: 25px;
                    line-height: 1.6;
                }
                a {
                    display: inline-block;
                    padding: 12px 25px;
                    background: #e74c3c;
                    color: #fff;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    transition: all 0.3s ease;
                    border: none;
                    cursor: pointer;
                }
                a:hover {
                    background: #c0392b;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ title }}</h1>
                <p>{{ message }}</p>
                <a href="javascript:history.back();">返回</a>
            </div>
        </body>
        </html>
        """,
        title=title,
        message=message
    )

async def base_success_page(title, message):
    return await render_template_string(
        """
        <!DOCTYPE html>
        <html lang="zh">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Roboto', sans-serif;
                    background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
                    color: #333;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }
                .container {
                    max-width: 500px;
                    width: 100%;
                    background: #fff;
                    border-radius: 12px;
                    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
                    padding: 30px;
                    text-align: center;
                    animation: fadeIn 0.5s ease;
                }
                h1 {
                    font-size: 24px;
                    color: #2ecc71;
                    margin-bottom: 20px;
                    position: relative;
                    padding-bottom: 10px;
                }
                h1:after {
                    content: '';
                    position: absolute;
                    bottom: 0;
                    left: 50%;
                    transform: translateX(-50%);
                    width: 50px;
                    height: 3px;
                    background: #2ecc71;
                }
                p {
                    font-size: 16px;
                    color: #555;
                    margin-bottom: 25px;
                    line-height: 1.6;
                }
                a {
                    display: inline-block;
                    padding: 12px 25px;
                    background: #2ecc71;
                    color: #fff;
                    text-decoration: none;
                    border-radius: 8px;
                    font-weight: bold;
                    transition: all 0.3s ease;
                    border: none;
                    cursor: pointer;
                }
                a:hover {
                    background: #27ae60;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ title }}</h1>
                <p>{{ message }}</p>
                <a href="javascript:history.back();">返回</a>
            </div>
        </body>
        </html>
        """,
        title=title,
        message=message
    )