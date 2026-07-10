"""
streamlit-cropper 패키지의 번들 프론트엔드(JS)에는 크롭 박스를 캔버스(=미리보기
이미지) 경계 안으로 붙잡아두는 로직이 없다. 그래서 박스를 가장자리로 드래그하거나
모서리로 크기를 조절하면 박스가 캔버스 밖으로 나가고, <canvas>는 자기 픽셀 영역
밖은 그리지 않으므로 잘려 보이는 문제가 발생한다.

패키지 자체를 고칠 수 없으므로(pip 재설치 시 원본으로 되돌아감), pip install 직후
이 스크립트를 실행해 번들 JS에 경계 clamp 로직을 주입한다. 이미 패치되어 있으면
아무 것도 하지 않으므로 여러 번 실행해도 안전하다 (build_exe.bat에서 매 빌드마다
자동으로 호출됨).
"""

import glob
import os
import sys

import streamlit_cropper

PATCH_MARKER = "__imageToolkitCropClampPatch"

ORIGINAL_SNIPPET = "g.add(p),s.current=p,n(g),f.setFrameHeight(),()=>{g.dispose()}"

# 상태(직전 정상 위치 등)를 기억하지 않고, 매 이벤트마다 "현재" 위치/크기만 보고
# 캔버스 범위를 벗어난 만큼을 그 자리에서 되돌린다. 상태를 기억하는 방식(lastGood
# 스냅샷)은 박스가 생성된 후 첫 리사이즈에서 곧바로 경계를 넘으면 되돌아갈 기록이
# 없어 clamp가 무력화되고, 그 이후로도 계속 커진 채 고정되는 문제가 있었다
# (__imageToolkitCropClampPatch 마커명은 그대로 재사용해 이전 패치를 덮어쓴다).
CLAMP_JS = (
    "(function(){"
    f"function {PATCH_MARKER}(tgt,canvas){{"
    "var cw=canvas.getWidth(),ch=canvas.getHeight(),b=tgt.getBoundingRect();"
    "if(b.width>cw){tgt.scaleX*=cw/b.width;}"
    "if(b.height>ch){tgt.scaleY*=ch/b.height;}"
    "tgt.setCoords();"
    "b=tgt.getBoundingRect();"
    "if(b.left<0)tgt.left-=b.left;"
    "if(b.top<0)tgt.top-=b.top;"
    "b=tgt.getBoundingRect();"
    "if(b.left+b.width>cw)tgt.left-=(b.left+b.width-cw);"
    "if(b.top+b.height>ch)tgt.top-=(b.top+b.height-ch);"
    "tgt.setCoords();"
    "}"
    f"g.on('object:moving',(function(opt){{{PATCH_MARKER}(opt.target,g)}}));"
    f"g.on('object:scaling',(function(opt){{{PATCH_MARKER}(opt.target,g)}}));"
    "})(),"
)


def find_bundle_js_path() -> str:
    """설치된 streamlit_cropper 패키지의 번들 JS 파일 경로를 찾는다."""
    package_dir = os.path.dirname(streamlit_cropper.__file__)
    candidates = glob.glob(os.path.join(package_dir, "frontend", "build", "static", "js", "main.*.js"))
    if not candidates:
        raise FileNotFoundError("streamlit_cropper 번들 JS 파일을 찾을 수 없습니다.")
    return candidates[0]


def apply_patch() -> None:
    bundle_path = find_bundle_js_path()
    with open(bundle_path, "r", encoding="utf-8") as bundle_file:
        content = bundle_file.read()

    if PATCH_MARKER in content:
        print(f"[patch_streamlit_cropper] 이미 패치되어 있습니다: {bundle_path}")
        return

    if ORIGINAL_SNIPPET not in content:
        print(
            "[patch_streamlit_cropper] 경고: 예상한 원본 코드를 찾지 못했습니다 "
            "(streamlit-cropper 버전이 바뀐 것 같습니다). 패치를 건너뜁니다.",
            file=sys.stderr,
        )
        return

    patched_content = content.replace(
        ORIGINAL_SNIPPET,
        "g.add(p),s.current=p,n(g),f.setFrameHeight()," + CLAMP_JS + "()=>{g.dispose()}",
        1,
    )
    with open(bundle_path, "w", encoding="utf-8") as bundle_file:
        bundle_file.write(patched_content)

    print(f"[patch_streamlit_cropper] 패치 완료: {bundle_path}")


if __name__ == "__main__":
    apply_patch()
