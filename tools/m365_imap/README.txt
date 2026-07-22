# Outlook / Hotmail 重新获取 refresh_token（M365-IMAP 方案）
#
# 依赖已用清华源 wheel 安装：msal、PyJWT
#
# 用法（会打开浏览器，用对应 Hotmail 登录授权）：
#   cd tools/m365_imap
#   python get_token.py
#
# 成功后当前目录生成：
#   imap_smtp_refresh_token
#   imap_smtp_access_token
#
# 再导出成项目格式：
#   python export_pool_line.py 你的邮箱@hotmail.com 你的密码
#
# 输出一行：
#   email----password----9e5f94bc-e8a4-4e73-b8be-63364c29d753----refresh_token
#
# 把该行追加到项目根目录 用于注册的邮箱.txt
