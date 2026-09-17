from pathlib import Path
import yaml

_path = Path(__file__).resolve().parents[1] / "config" / "mappings.yaml"
mappings: dict = yaml.safe_load(_path.read_text())
