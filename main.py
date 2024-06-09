"""
程序入口点。
"""

from collections import Counter
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
    latest_time = None

    # 遍历文件夹中的所有文件和子文件夹
    for path in folder.rglob("*"):
        # 忽略子文件夹和符号链接等
        if path.is_file() and not path.is_symlink():
            # 获取文件的修改时间
            mod_time = os.path.getmtime(path)
            # 如果没有找到文件，或者当前文件的修改时间比已找到的文件晚
            if latest_time is None or mod_time > latest_time:
                latest_time = mod_time
                latest_file = path

    return latest_file


class Minecraft:
    """
    .minecraft 文件夹。
    """

    path: Path
    """.minecraft 路径。"""

    def __init__(self, path: Path) -> None:
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
        return Saves(self.path / "saves")

    def __str__(self) -> str:
        return self.path.name


class Saves:
    """
    存档文件夹。
    """

    path: Path
    """saves 文件夹路径。"""
    versioned: bool = True
    """是否为版本隔离存档。"""

    def __init__(self, path: Path, versioned: bool = True):
        self.path = path
        self.versioned = versioned

    def __iter__(self):
        return (Save(s) for s in self.path.iterdir())


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
        print(f"正在修复存档：{self.path}")
        adv_json = latest_modified(self.path / "advancements")
        if not adv_json:
            print("该存档不需要修复！")
            return
        if adv_json and adv_json.suffix != ".json":
            raise ValueError(f"存档中可能有个人文件，修复失败（{adv_json}）。")
        adv_json.rename(adv_json.parent / f"{new_uuid}.json")
        print(f"{adv_json} -> {adv_json.parent / f'{new_uuid}.json'}")
        print("修复成功！")

    def __str__(self) -> str:
        return self.path.name


class ListSelect:
    """
    让用户选择列表中的一项。
    """

    def __init__(self, to_select: list, hint_text: str = "") -> None:
        self.to_select = to_select
        self.hint_text = hint_text

    def select(self):
        """
        让用户选择。
        """
        for i in range(len(self.to_select)):  # pylint: disable=C0200
            print(f"[{i + 1}] {self.to_select[i]}")
        selected = input(f"{self.hint_text}（输入编号，然后按下 Enter）：")
        if is_int(selected):
            return self.to_select[int(selected) - 1]
        return None


class UuidReader:
    """
    读取 UUID。
    """

    POSSIBLE_BATCH = ["../PCL/LatestLaunch.bat"]
    possible_uuid = []

    def __init__(self, mc_path: Path) -> None:
        self.mc_path = mc_path

    def read(self):
        """
        读取 UUID。
        """
        for p in self.POSSIBLE_BATCH:
            if not (path := self.mc_path / p).exists():
                continue
            with open(path, "r", encoding="ansi") as f:
                content = f.read()
            match = re.search(r"--uuid\s+(\S+)", content)
            if not match:
                continue
            self.possible_uuid.append(match[0].replace("--uuid", "").strip())
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
        result = ListSelect(list(self.mc), "请选择游戏版本").select()
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
        让用户选择存档。
        """
        result = ListSelect(list(self.saves), "请选择存档").select()
        if not result:
            print("未知的存档。")
            return False
        if not isinstance(result, Save):
            return False
        result.fix(UuidReader(self.mc.path).read())
        return True

    def read_uuid(self):
        """
        获取用户 UUID。
        """
        UuidReader(self.mc.path).read()

    def run_all(self):
        """
        运行一次程序逻辑。
        """
        return self.ask_minecraft() and self.ask_version() and self.ask_save()


def main():
    """
    主函数。
    """
    while True:
        Logic().run_all()


if __name__ == "__main__":
    main()
