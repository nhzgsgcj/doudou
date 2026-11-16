# Pages CMS 使用说明（网页后台管理本相册）

这个仓库接入了 [Pages CMS](https://pagescms.org)——一个直接管理 GitHub 仓库内容的网页后台。
以后**加照片、删照片、改标题都不需要碰代码**，在网页里点几下就行。

## 一、开通后台（只需做一次）

1. 打开 **https://app.pagescms.org**，用 GitHub 账号登录；
2. 首次使用会要求安装 Pages CMS 的 GitHub App，按提示授权给仓库 `nhzgsgcj/doudou`；
3. 在应用里选中 `doudou` 仓库，就能看到两个栏目：
   - **站点设置**——改大标题、副标题、页脚文字；
   - **照片**——增删照片、写说明、改日期。

## 二、日常怎么加照片

1. 打开 `app.pagescms.org` → 进入 **照片** 栏目；
2. 点新建 → **图片** 字段里上传照片（自动存入 `resource/jpg/`，文件名保持不变）；
3. 可选填"说明"和"拍摄日期"；
4. 点 **Save**，Pages CMS 会自动 commit 到仓库；
5. 等 30–60 秒，GitHub Pages 自动重新发布，刷新页面即可看到新照片。

## 三、配置在哪里

后台能编辑什么、图片传到哪里，全部由仓库根目录的 **`.pages.yml`** 定义：

| 配置 | 作用 |
|---|---|
| `media.input: resource/jpg` | 上传的照片存放目录 |
| `content[].path: data/photos.json` | 照片清单（页面读取它来渲染瀑布流） |
| `content[].path: data/site.json` | 标题/副标题/页脚 |

想加新的栏目（比如"视频"、"留言"），改 `.pages.yml` 即可，参考
[官方文档](https://pagescms.org/docs/configuration/)。

## 四、注意事项

- **仓库是公开的**，照片任何人可见，别放隐私照；
- Pages CMS 上传的是**原图**，手机拍的 5MB 一张，照片多了仓库会接近 1GB 建议上限，建议先压缩再上传；
- `index.html` 里内置了 23 张旧照片的兜底列表，只在 JSON 加载失败时使用；正常情况以 `data/photos.json` 为准；
- 本地预览：`python -m http.server 8899` 后访问 http://127.0.0.1:8899/ （直接双击 index.html 会因为浏览器限制读不到 JSON，会走兜底列表）。
