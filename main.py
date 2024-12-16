from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
import humanize
import subprocess
import logging
import os

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# 使用绝对路径
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

class VideoDownloader:
    def download_video(self, url):
        try:
            # 提取BV号
            if 'BV' in url:
                bv_id = url.split('BV')[1].split('?')[0].split('/')[0]
                url = f"https://www.bilibili.com/video/BV{bv_id}"
            
            logger.info(f"开始下载: {url}")
            
            # 检查yt-dlp是否安装
            try:
                version_cmd = subprocess.run(
                    ['yt-dlp', '--version'],
                    capture_output=True,
                    text=True
                )
                logger.info(f"yt-dlp 版本: {version_cmd.stdout.strip()}")
            except FileNotFoundError:
                logger.error("yt-dlp 未安装")
                return {'error': '请先安装 yt-dlp: pip install yt-dlp'}
            
            # 确保下载目录存在
            DOWNLOAD_DIR.mkdir(exist_ok=True)
            logger.info(f"下载目录: {DOWNLOAD_DIR}")
            
            try:
                # 使用yt-dlp下载，修改格式选择参数
                cmd = [
                    'yt-dlp',
                    '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # 更精确的格式选择
                    '--merge-output-format', 'mp4',  # 确保输出MP4格式
                    '--no-warnings',  # 抑制警告信息
                    '-o', str(DOWNLOAD_DIR / '%(title)s.%(ext)s'),  # 使用完整路径
                    url
                ]
                logger.info(f"执行命令: {' '.join(cmd)}")
                
                # 使用 subprocess.run 执行命令
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    logger.error(f"下载失败: {result.stderr}")
                    return {'error': f'下载失败: {result.stderr}'}
                
                logger.info(f"命令输出: {result.stdout}")
                
                # 检查新下载的MP4文件
                files = list(DOWNLOAD_DIR.glob('*.mp4'))
                if files:
                    # 获取最新的文件
                    video_file = max(files, key=lambda x: x.stat().st_mtime)
                    return {
                        'title': video_file.stem,
                        'filepath': video_file.name,
                        'filesize': humanize.naturalsize(video_file.stat().st_size),
                        'status': 'success'
                    }
                
                logger.error("未找到下载的视频文件")
                return {'error': '下载完成但未找到视频文件'}
                
            except Exception as e:
                logger.error(f"下载过程出错: {str(e)}")
                import traceback
                logger.error(f"错误堆栈:\n{traceback.format_exc()}")
                return {'error': f'下载出错: {str(e)}'}
            
        except Exception as e:
            logger.error(f"处理过程出错: {str(e)}")
            import traceback
            logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            return {'error': f'处理出错: {str(e)}'}

@app.get("/")
async def home(request: Request):
    videos = []
    for file in DOWNLOAD_DIR.glob("*.mp4"):
        videos.append({
            'title': file.stem,
            'filepath': f"/downloads/{file.name}",
            'filesize': humanize.naturalsize(file.stat().st_size)
        })
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "videos": videos}
    )

@app.post("/download")
async def download_video(request: Request):
    logger.info("=== 开始下载处理 ===")
    try:
        data = await request.json()
        logger.info(f"收到的请求数据: {data}")
        
        urls = data.get('urls', '').split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        logger.info(f"处理后的URL列表: {urls}")
        
        if not urls:
            logger.warning("没有提供有效的URL")
            return JSONResponse(content=[{'error': '请提供有效的视频链接'}])
            
        downloader = VideoDownloader()
        results = []
        for url in urls:
            result = downloader.download_video(url)
            results.append(result)
            logger.info(f"URL {url} 的下载结果: {result}")
        
        return JSONResponse(content=results)
        
    except Exception as e:
        error_msg = f"发生错误: {str(e)}"
        logger.error(error_msg)
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return JSONResponse(content=[{'error': error_msg}])