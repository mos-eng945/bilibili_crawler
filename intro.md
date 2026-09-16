## login.py

产出 bilibili_state.json用来保存你的登陆cookie避免重复登陆



### load_state()-->boolean

 读cookie

### has_cookie()-->boolean

cookies.cookie.SESSDATA (识别登陆状态的 ).expires(cookie过期时间)







### get_cookie_header()

如果不传cookie调用bilibili_state.json里面cookie,有传state 自己构造



### check_login_online()-->boolean

​    构造request,向"https://api.bilibili.com/x/web-interface/nav"探测

查看response里面的   isLogin":true 

### login()

打开浏览器，人工登录，然后把 cookie 存STATE_FILE(bilibili_state.json)



### ensure_login()

```python
def ensure_login():
    """有可用 cookie 就跳过登录，否则弹出浏览器手动登录"""
    if not has_cookie():
        login()
        return

    if check_login_online():
        print("检测到有效登录状态，跳过登录")
        return

    print("cookie 已失效，重新登录")
    login()
```

## bilibili_api.py



通用函数



MIXIN_KEY_ENC_TAB = [

46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30, 4,22,25, 54,21,56,59,6,63,57,62,11,36,20, 34,44,52,

]



### request_json()-->{} <!--  data -->

请求url,并接受response

`````json
{
  "code": 0,
  "message": "0",
  "ttl": 1,
  "data": {
    "...": "..."
  }
}

`````

code:0 正常返回

message 信息

data 业务数据

ttl：接口数据的缓存或有效时间相关信息，不代表登录状态有效期。



### get_wbi_mixin_key()

生成mixin_key

`````
        "wbi_img": {
            "img_url": "https://i0.hdslb.com/bfs/wbi/7cd084941338484aae1ad9425b84077c.png",
            "sub_url": "https://i0.hdslb.com/bfs/wbi/4932caff0ff746eab6f01bf08b70ac45.png"
        },
`````



从https://api.bilibili.com/x/web-interface/nav获得7cd084941338484aae1ad9425b84077c和4932caff0ff746eab6f01bf08b70ac45拼接得到raw_key 在通过字符重排表取前32为得到mixin key

返回32位mixin_key



### sign_wbi_params

生成WBI签名

给原参数加入当前 Unix 时间戳 `wts`。

按参数名排序并进行 URL 编码，得到规范化查询字符串。 



```
bvid=BV1xx&cid=123&wts=1780000000
```



把查询字符串和 `mixin_key` 拼接后计算 MD5。

把 MD5 结果作为 `w_rid` 追加到查询字符串中

```
return f"{query}&w_rid={w_rid}"
```





### request_wbi_json() 

请求需要wbi签名的接口

```
 return request_json(f"{API_BASE}{path}?{query}", cookie)

```





###  get_video_info()

https://api.bilibili.com/x/web-interface/view?bvid=BV1SdYn6cEoq

访问video接口信息



### get_video_pages()

复用get_video_info()

```
pages": [
      {
        "cid": 41705210202,
        "page": 1,
        "from": "vupload",
        "part": "studio_video_1788892334602.mp4",
        "duration": 451,
        "vid": "",
        "weblink": "",
        "dimension": {
          "width": 1920,
          "height": 1080,
          "rotate": 0
        },
        "first_frame": "http://i2.hdslb.com/bfs/storyff/_00000ojmmear7afnd2rqlozb8kjicmb_firsti.jpg",
        "ctime": 1788892522
      }
    ],
```

 ```
   return data.get("pages", [])
 ```











