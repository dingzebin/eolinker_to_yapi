import html
import json
import http.client, urllib.parse

yapi_cookie = "yapi cookie"
yapi_host = "yapi host"

eolinker_cookie = "eolinker cookie"
eolinker_host = "eolinker host"


# 请求方式转换
methods = {
  0: "POST",
  1: "GET",
  2: "PUT",
  3: "DELETE",
  4: "HEAD",
  5: "OPTIONS",
  6: "PATCH"
}

############### yapi 接口调用 ##############
# yapi的创建接口请求
def yapiReq(uri, params):
  headers = {
    "Content-type": "application/json;charset=UTF-8",
    "Cookie": yapi_cookie,
    "Accept": "application/json, text/plain, */*"
  }
  conn = http.client.HTTPSConnection(yapi_host)
  conn.request("POST", uri, bytes(json.dumps(params), "utf-8"), headers)
  return conn.getresponse().read().decode("utf-8")

def getPublicClassification(project_id): 
  headers = {
    "Content-type": "application/json;charset=UTF-8",
    "Cookie": yapi_cookie,
    "Accept": "application/json, text/plain, */*"
  }
  conn = http.client.HTTPSConnection(yapi_host)
  conn.request("GET", "/api/interface/getCatMenu?project_id=" + str(project_id), headers=headers)
  return json.loads(conn.getresponse().read().decode("utf-8"))["data"][0]

# 添加分组
def addGroup(groupName):
  return json.loads(yapiReq("/api/group/add", {
    "group_name": groupName, 
    "owner_uids": [],
    "group_desc": ""
  }))["data"]["_id"]


# 添加项目, 返回项目id
def addProject(projectName, groupId):
  return json.loads(yapiReq("/api/project/add", {
    "name": projectName, 
    "basepath":"",
    "group_id": groupId,
    "icon":"code-o",
    "color":"pink",
    "project_type":"private"
  }))["data"]["_id"]

# 添加分类
def addCat(name, projectId):
  return json.loads(yapiReq("/api/interface/add_cat", {
    "name": name, 
    "project_id": projectId
  }))["data"]["_id"]

###### eolinker 接口调用 ##############

# eolinker request
def eolinker_req(uri, params):
  headers = {
    "Content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Cookie": eolinker_cookie,
    "Accept": "application/json, text/plain, */*",
  }
  conn = http.client.HTTPConnection(eolinker_host)
  conn.request("POST", uri, urllib.parse.urlencode(params), headers=headers)
  return conn.getresponse().read().decode("utf-8")


###### 处理接口转换 ##################

def process(data):
  groupJson = json.loads(data)
  # 分组
  groupId = addGroup(groupJson["projectInfo"]["projectName"])
  for group in groupJson["apiGroupList"]:
    projectId = addProject(group["groupName"], groupId)
    if type(group["apiGroupChildList"]) == dict:
      for groupChild in group["apiGroupChildList"].values():
        if groupChild.get("groupName") is not None:
          handleSecondLevel(groupChild, projectId, groupId)
    else:
      for groupChild in group["apiGroupChildList"]:
        if groupChild.get("groupName") is not None:
          handleSecondLevel(groupChild, projectId, groupId)
    # 没有二级目录的放到公共分类
    cat = getPublicClassification(projectId)
    handleApi(group.get("apiList"), None, cat["_id"], cat["name"], projectId, groupId)

# 处理二级分类
def handleSecondLevel(second, projectId, groupId): 
  catid = addCat(second["groupName"], projectId)
  # print("-" + second["groupName"] + "-")

  # 有三级分类的
  if second.get("apiGroupChildList") is not None:
    for group in second["apiGroupChildList"]:
      handleApi(group.get("apiList"), group.get("groupName"), catid, second["groupName"], projectId, groupId)
  # 只有二级分类
  handleApi(second.get("apiList"), None, catid, second["groupName"], projectId, groupId)

# 处理api
def handleApi(apiList, thirdClassificationName, catid, catname, projectid, groupid):
  if apiList is not None:
    if type(apiList) == dict:
      for api in apiList.values():
        addApi(api, thirdClassificationName, catid, catname, projectid, groupid)
    else:
      for api in apiList:
        addApi(api, thirdClassificationName, catid, catname, projectid, groupid)

# 添加api
def addApi(api, thirdClassificationName, catid, catname, projectid, groupid):
  if is_contains_chinese(api['baseInfo']['apiURI']):
    print("URI错误 =>" + api['baseInfo']['apiURI'])
    return
  api['baseInfo']['apiURI'] = api['baseInfo']['apiURI'].replace("$", "").replace("(", "{").replace(")", "}")
  api['baseInfo']['apiURI'] = api['baseInfo']['apiURI'] if api['baseInfo']['apiURI'].find("/") == 0 else ("/" + api['baseInfo']['apiURI'])
  params = {
    "catid": catid,
    "catname": catname,
    "dataSync": "merge",
    "path": api['baseInfo']['apiURI'],
    "project_id": projectid,
    "query_path": {
      "path": api['baseInfo']['apiURI'],
      "params": []          
    },
    "status": "done",
    "type": "static",
    "method": methods.get(api['baseInfo']['apiRequestType'], "POST"),
    "title": ((thirdClassificationName + "-") if thirdClassificationName is not None else "")  + api['baseInfo']['apiName'],
    "res_body_type": "json",
    "res_body": api['baseInfo']['apiSuccessMock']    
  }
  # Get请求
  if params["method"] == "GET":
    if api.get("requestInfo") is not None:
      params["req_query"] = []
      for reqInfo in api.get("requestInfo"):
        params["req_query"].append({
            "required": "1" if reqInfo["paramNotNull"] == "0" else "0",
            "name": reqInfo["paramKey"],
            "example": reqInfo["paramValue"],
            "desc": reqInfo["paramName"],
            "type": "text",
        })
  else:
    # POST 请求判断有没有raw，有的话优先使用raw
    if api['baseInfo']['apiRequestRaw']:
      params["req_body_type"] = "raw"
      params["req_body_other"] = html.unescape(api['baseInfo']['apiRequestRaw'])
    else:
      # 没有的话获取表单
      params["req_body_type"] = "form"
      if api.get("requestInfo") is not None:
        params["req_headers"] = [
          {
            "required": "1",
            "name": "Content-Type",
            "value": "application/x-www-form-urlencoded"
          }
        ]
        params["req_body_form"] = []
        for reqInfo in api.get("requestInfo"):
          params["req_body_form"].append({
              "required": "1" if reqInfo["paramNotNull"] == "0" else "0",
              "name": reqInfo["paramKey"],
              "example": reqInfo["paramValue"],
              "type": "text",
              "desc": reqInfo["paramName"]
          })

  r = json.loads(yapiReq("/api/interface/save", params))
  if r["errcode"] != 0:
    # print(r)
    print("URI错误 =>" + params["path"])
    # raise RuntimeError('add api error')

# 判断是否含有中文
def is_contains_chinese(strs):
    for _char in strs:
        if '\u4e00' <= _char <= '\u9fa5':
            return True
    return False


# 获取eolinker的项目
projectListInfo = json.loads(eolinker_req("/server/index.php?g=Web&c=Project&o=getProjectList", {
  "projectType": -1
}))
for project in projectListInfo["projectList"]:
  # 获取下载文件信息
  downloadInfo = json.loads(eolinker_req("/server/index.php?g=Web&c=Project&o=dumpProject", {"projectID": project["projectID"]}))
  conn = http.client.HTTPConnection(eolinker_host)
  # 下载文件
  conn.request("GET", "/server/dump/" + downloadInfo["fileName"])
  data = conn.getresponse().read()
  print("开始同步 %s ....." % (project["projectName"]))
  process(data)
  print("%s 同步结束.\n" % (project["projectName"]))
  conn.close()

print("同步完成... 请检查错误的URI然后手动添加接口, URI只支持 数字英文字母和-/_:.! ")