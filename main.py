"""
程序入口点。
"""

from collections import Counter
import datetime
import json
import os
from pathlib import Path
import re
import uuid


def is_int(val):
    """
    判断 val 是否可转为 int。
    """
    try:
        int(val)
        return True
    except ValueError:
        return False


def latest_modified(folder: Path):
    """
    获取 `folder` 下最晚被修改的文件。
    """
    latest_file = None
    latest_time = -1.0

    # 遍历文件夹中的所有文件和子文件夹
    for path in folder.rglob("*"):
        # 忽略子文件夹和符号链接等
        if not path.is_file() or path.is_symlink():
            continue
        # 获取文件的修改时间
        mod_time = os.path.getmtime(path)
        # 如果没有找到文件，或者当前文件的修改时间比已找到的文件晚
        if mod_time > latest_time:
            latest_time = mod_time
            latest_file = path

    return latest_file


def askfor_select(to_select: list, hint: str):
    """
    让用户选择列表中的一项。
    """
    for i in range(len(to_select)):  # pylint: disable=C0200
        print(f"[{i + 1}] {to_select[i]}")
    selected = input(f"{hint}（输入编号，然后按下 Enter）：")
    if is_int(selected) and 1 <= int(selected) <= len(to_select):
        return to_select[int(selected) - 1]
    return None


class Minecraft:
    """
    .minecraft 文件夹。
    """

    path: Path
    """.minecraft 路径。"""

    def __init__(self, path: Path) -> None:
        if not path.is_dir():
            raise FileNotFoundError(f"错误：未找到 .minecraft 文件夹：{path}")
        self.path = path

    def __iter__(self):
        return (Version(v) for v in self.versions.iterdir())

    @property
    def versions(self):
        """
        版本文件夹。
        """
        if not self.path:
            raise ValueError("未指定 .minecraft 路径。")
        return self.path / "versions"

    @property
    def saves(self):
        """
        存档文件夹（未版本隔离）。
        """
        if not self.path:
            raise ValueError("未指定 .minecraft 路径。")
        return Saves(self.path / "saves")


class Version:
    """
    游戏版本。
    """

    path: Path
    """游戏版本路径。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __iter__(self):
        yield from self.saves

    @property
    def saves(self):
        """
        存档文件夹。
        """
        if not self.path:
            raise ValueError("未指定版本路径。")
        if not self.path.is_dir():
            raise FileNotFoundError(f"错误：未找到版本文件夹：{self.path}")
        return Saves(self.path / "saves")

    def __str__(self) -> str:
        return self.path.name


class Saves:
    """
    存档文件夹。
    """

    path: Path
    """saves 文件夹路径。"""

    def __init__(self, path: Path):
        if not path.name == "saves":
            raise ValueError(f"错误：不是有效的 saves 文件夹：{path}")
        self.path = path

    def __iter__(self):
        if not self.path.is_dir():
            raise FileNotFoundError(f"错误：未找到 saves 文件夹：{self.path}")
        return (Save(s) for s in self.path.iterdir())

    def __str__(self) -> str:
        return "未开启版本隔离"


class SaveFixError(Exception):
    """
    存档修复时出现的问题。
    """

    save: "Save"
    """存档。"""

    def __init__(self, msg: str, save: "Save") -> None:
        self.msg = msg
        self.save = save

    def __str__(self) -> str:
        return f"修复 {self.save} 失败：{self.msg}"


class Save:
    """
    存档。
    """

    path: Path
    """存档路径。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def fix(self, new_uuid: str):
        """
        修复存档。
        """
        if not self.path.is_dir():
            raise FileNotFoundError(f"错误：未找到存档文件夹：{self.path}")
        print(f"正在修复存档：{self.path}")
        adv_json = latest_modified(self.path / "advancements")
        if not adv_json:
            print("该存档不需要修复！")
            return
        if adv_json and adv_json.suffix != ".json":
            raise SaveFixError(f"存档中可能有个人文件，修复失败（{adv_json}）。", self)
        adv_json.rename(adv_json.parent / f"{new_uuid}.json")
        print(f"{adv_json} -> {adv_json.parent / f'{new_uuid}.json'}")
        print("修复成功！")

    def __str__(self) -> str:
        return self.path.name


class UuidReader:
    """
    读取 UUID。
    """

    POSSIBLE_BATCH = ["../PCL/LatestLaunch.bat"]
    possible_uuid = []

    def __init__(self, mc_path: Path, usercache: Path) -> None:
        self.mc_path = mc_path
        self.usercache = usercache

    def read(self):
        """
        读取 UUID。
        """
        for p in self.POSSIBLE_BATCH:
            if not (path := self.mc_path / p).is_file():
                continue
            with open(path, "r", encoding="ansi") as f:
                content = f.read()
            match = re.search(r"--uuid\s+(\S+)", content)
            if not match:
                continue
            self.possible_uuid.append((u := match[0].replace("--uuid", "").strip()))
            print(f"[UUID] 从启动脚本获取到的 UUID：{u}")
        if self.usercache.is_file():
            with open(self.usercache, "r", encoding="utf-8") as f:
                content = json.load(f)
            if isinstance(content, dict):
                self.possible_uuid.append(
                    *(
                        d["uuid"]
                        for d in content
                        if datetime.datetime.fromisoformat(d["expiresOn"])
                        > datetime.datetime.now()
                    )
                )
        print("[UUID] 读取到的 UUID：", self.possible_uuid)
        common = Counter(self.possible_uuid).most_common(1)
        if not common:
            return self.format(input("自动读取 UUID 失败，请手动输入 UUID："))
        return self.format(common[0][0])

    def format(self, uuid_input: str):
        """
        格式化 UUID。
        """
        print(uuid_input, str(uuid.UUID(uuid_input)).lower())
        return str(uuid.UUID(uuid_input)).lower()


class Logic:
    """
    运行逻辑类。
    """

    mc: Minecraft
    """.minecraft 文件夹。"""

    def ask_minecraft(self):
        """
        询问用户 .minecraft 文件夹位置。
        """
        path = Path(input("请将 .minecraft 文件夹拖拽至此处，然后按下 Enter："))
        if not path.is_dir():
            print("文件夹不存在。")
            return False
        self.mc = Minecraft(path)
        return True

    def ask_version(self):
        """
        让用户选择游戏版本。
        """
        version_list = ([self.mc.saves] if self.mc.saves.path.is_dir() else []) + list(
            self.mc
        )
        if len(version_list) == 0:
            print("没有游戏版本。")
            return False
        result = askfor_select(
            version_list,
            "请选择游戏版本",
        )
        if not result:
            print("未知的游戏版本。")
            return False
        if isinstance(result, Saves):
            # 没开版本隔离
            self.saves = result
        elif isinstance(result, Version):
            # 版本隔离了
            self.saves = result.saves
        return True

    saves: Saves
    """saves 文件夹。"""

    def ask_save(self):
        """
        让用户选择存档并修复。
        """
        if len(saves_list := list(self.saves)) == 0:
            print("没有存档。")
            return False
        result = askfor_select(saves_list, "请选择存档")
        if not result:
            print("未知的存档。")
            return False
        if not isinstance(result, Save):
            return False
        result.fix(
            UuidReader(
                self.mc.path, result.path / ".." / ".." / "usercache.json"
            ).read()
        )
        return True

    def run_all(self):
        """
        运行一次程序逻辑。
        """
        print("请尽量在修复前启动一次游戏，加载完成后将其关闭，可以增加修复准确度。")
        # 如果任何一步运行失败，那么就短路返回 False
        # 应 Silverteal 意见，加一个注释（
        return self.ask_minecraft() and self.ask_version() and self.ask_save()


def main():
    """
    主函数。
    """
    while True:
        Logic().run_all()


if __name__ == "__main__":
    main()
