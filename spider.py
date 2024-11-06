import aiohttp
import asyncio
import re
import pickle
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector

HOST = 'https://concours-maths-cpge.fr/'
HEADERS = {
    "accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding":"gzip, deflate, br",
    "accept-language":"zh-CN,zh;q=0.9",
    "cache-control":"no-cache",
    "dnt":"1",
    "origin":"https://concours-maths-cpge.fr",
    "pragma":"no-cache",
    "referer":"https://concours-maths-cpge.fr/",
    "sec-fetch-dest":"document",
    "sec-fetch-mode":"navigate",
    "sec-fetch-site":"same-origin",
    "sec-fetch-user":"?1",
    "upgrade-insecure-requests":"1",
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36"
}

async def post(session, data):
    async with session.post(HOST, data=data) as resp:
        print(resp.status)
        return (await resp.text())


async def fetch_page():
    connector = ProxyConnector.from_url('socks5://127.0.0.1:7890')
    results = {}
    tasks = []

    async with aiohttp.ClientSession(connector=connector) as session:
        session.headers.update(HEADERS)

        # res = await post(session, {
        #     "cmd":"",
        #     "mode":"public",
        #     "commande":"connexion"
        # })
        # res = await post(session, {
        #     "cmd":"",
        #     "mode":"public",
        #     "annee":"1924-2023",
        #     "concours":"0",
        #     "filiere":"0",
        #     "matiere":"0",
        #     "epreuve":"0",
        #     "domaine":"0",
        #     "titre":"",
        #     "commande":"rechercher"
        # })
        # targets = re.findall(r'numero=(.*?)"', res)
        # print(res)
        # print(len(targets), targets)
        for i in range(0, 5650, 10): # 5605，搞多点看看会发生什么 # 结论：没用，给长度为0的列表
            tasks.append(asyncio.create_task(post(session, {
                "cmd":f"commande=rechercher|init={i}",
                "mode":"public",
                "annee":"1924-2023",
                "ordre":"-annee:+nom:+filiere:+matiere:+epreuve:+titre"
            })))
        task_res = await asyncio.gather(*tasks)
        for i in range(0, 5650, 10): # 5605，搞多点看看会发生什么
            targets = re.findall(r'numero=(.*?)"', task_res[i//10])
            results[i] = targets
            print(len(targets), i)
    with open('numero_list.pkl', 'wb') as f:
        pickle.dump(results, f)



async def get_md5():
    connector = ProxyConnector.from_url('socks5://127.0.0.1:7890')
    with open('numero_list.pkl', 'rb') as f:
        results = pickle.load(f)

    # results = {0: results[0], 10: results[10]}

    async def post_and_get_md5(session, data, file_id):
        res = await post(session, data)
        finds = re.findall(r'''commande=download\|md5=(.*?)"\)'>(.*?)<''', res)
        # finds有若干个项，有的是LaTeX，有的是pdf，可能有很多个latex和pdf，这里都得用列表存起来考虑
        with open('html/' + file_id + '.html', 'w', encoding='utf-8') as f:
            f.write(res) # 存一份html方便事后分析和归类文档
        return {file_id: finds}

    md5_res = {}
    async with aiohttp.ClientSession(connector=connector) as session:
        session.headers.update(HEADERS)
        tasks = []
        for page_init, file_ids in results.items():
            for file_id in file_ids: # numero
                tasks.append(asyncio.create_task(post_and_get_md5(session, {
                    "cmd":f"commande=rechercher|init={page_init}|numero={file_id}",
                    "mode":"public",
                    "annee":"1924-2023",
                    "ordre":"-annee:+nom:+filiere:+matiere:+epreuve:+titre"
                }, file_id)))
        task_res = await asyncio.gather(*tasks)
        for task_res_item in task_res:
            md5_res.update(task_res_item)

    with open('md5_res.pkl', 'wb') as f:
        pickle.dump(md5_res, f)

    print(md5_res)

async def download(session, data, md5):
    async with session.post(HOST, data=data) as resp:
        print(resp.status, md5)
        content_disposition = resp.headers.get('Content-Disposition')
        if content_disposition:
            # 使用正则表达式从Content-Disposition标头中提取文件名
            filename_match = re.search(r'filename="(.+)"', content_disposition)
            if filename_match:
                filename = filename_match.group(1)

                # 下载文件
                with open(f'file/{md5}-{filename}', 'wb') as f:
                    while True:
                        chunk = await resp.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)

async def get_file():
    connector = ProxyConnector.from_url('socks5://127.0.0.1:7890')
    with open('md5_res.pkl', 'rb') as f:
        md5_res = pickle.load(f) # {numero: [(md5, name), ...], ...}

    tasks = []

    async with aiohttp.ClientSession(connector=connector) as session:
        for _, v in md5_res.items():
            for md5, _ in v:
                tasks.append(asyncio.create_task(download(session, {
                    "cmd":f"commande=download|md5={md5}",
                    "mode":"public",
                    "annee":"1924-2023",
                    "ordre":"-annee:+nom:+filiere:+matiere:+epreuve:+titre"
                }, md5)))
                if len(tasks) >= 1:
                    await asyncio.gather(*tasks)
                    # await asyncio.sleep(2)
                    tasks.clear()

if __name__ == '__main__':
    asyncio.run(get_file())
