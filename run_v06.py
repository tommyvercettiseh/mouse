from __future__ import annotations

import customtkinter as ctk

import app as original_app
import run_fixed  # applies the v0.5 capture and replay fixes
from ai_mouse_lab.v06 import apply_patch
from ai_mouse_lab.v06_hotfix import apply_hotfix
from ai_mouse_lab.v061 import apply_patch as apply_v061_patch
from ai_mouse_lab.v062 import apply_patch as apply_v062_patch
from ai_mouse_lab.v063 import apply_patch as apply_v063_patch
from ai_mouse_lab.v064 import apply_patch as apply_v064_patch
from ai_mouse_lab.v070 import apply_patch as apply_v070_patch
from ai_mouse_lab.v071 import apply_patch as apply_v071_patch


def main() -> None:
    apply_patch(original_app)
    apply_hotfix(original_app)
    apply_v061_patch(original_app)
    apply_v062_patch(original_app)
    apply_v063_patch(original_app)
    apply_v064_patch(original_app)
    apply_v070_patch(original_app)
    apply_v071_patch(original_app)
    ctk.set_appearance_mode("dark")
    original_app.App().mainloop()


if __name__ == "__main__":
    main()
