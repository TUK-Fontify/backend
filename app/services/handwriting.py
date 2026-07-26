import os
import shutil
import fitz
import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path

UPLOAD_DIR = Path("/ksydev/Font/backend2/backend/uploads")

files = list(UPLOAD_DIR.glob("*.pdf")) + list(UPLOAD_DIR.glob("*.png"))

if not files:
    raise ValueError("upload 폴더에 PDF 또는 PNG 파일이 없습니다.")

INPUT_PATH = str(files[0])   # 첫 번째 파일 사용
extension = Path(INPUT_PATH).suffix.lower()

# 기본 설정
OUTPUT_SIZE = 128
CHARACTER_SIZE = 104
BLACK_THRESHOLD = 165
OUTPUT_DIR = "/ksydev/Font/backend2/backend/app/services/output"
DEBUG_DIR = "/ksydev/Font/backend2/backend/app/services/debug"

print(os.path.abspath(OUTPUT_DIR))

letters = [
    "가", "나", "더", "려", "모", "부", "쇼",
    "야", "져", "쵸", "켜", "튜", "프", "히"
]

if extension not in [".pdf", ".png"]:
    raise ValueError(
        "PDF 또는 PNG 파일만 사용할 수 있습니다.\n"
        f"현재 업로드된 형식: {extension}"
    )

for folder in [OUTPUT_DIR, DEBUG_DIR]:

    if os.path.exists(folder):
        shutil.rmtree(folder)

    os.makedirs(folder, exist_ok=True)


PAGE_IMAGE_PATH = os.path.join(
    DEBUG_DIR,
    "input_page.png"
)

if extension == ".pdf":

    document = fitz.open(INPUT_PATH)

    if len(document) == 0:
        document.close()
        raise ValueError("PDF에 페이지가 없습니다.")

    page = document.load_page(0)
    zoom = 4

    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(zoom, zoom),
        alpha=False
    )

    pixmap.save(PAGE_IMAGE_PATH)
    document.close()

elif extension == ".png":

    uploaded_image = cv2.imread(INPUT_PATH)

    if uploaded_image is None:
        raise ValueError("PNG 파일을 불러오지 못했습니다.")

    cv2.imwrite(
        PAGE_IMAGE_PATH,
        uploaded_image
    )

    print("PNG 이미지를 그대로 사용합니다.")


page_image = cv2.imread(PAGE_IMAGE_PATH)

if page_image is None:
    raise ValueError("작업용 이미지를 불러오지 못했습니다.")

page_height, page_width = page_image.shape[:2]

def create_purple_mask(image):
    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV
    )

    lower_purple = np.array(
        [110, 20, 35],
        dtype=np.uint8
    )

    upper_purple = np.array(
        [179, 255, 255],
        dtype=np.uint8
    )

    hsv_mask = cv2.inRange(
        hsv,
        lower_purple,
        upper_purple
    )

    blue, green, red = cv2.split(image)

    blue16 = blue.astype(np.int16)
    green16 = green.astype(np.int16)
    red16 = red.astype(np.int16)

    bgr_mask = (
        (red16 > green16 + 3)
        &
        (blue16 > green16 + 3)
        &
        (red16 > 70)
        &
        (blue16 > 70)
    ).astype(np.uint8) * 255

    return cv2.bitwise_or(
        hsv_mask,
        bgr_mask
    )

purple_mask = create_purple_mask(page_image)

purple_mask[
    :int(page_height * 0.38),
    :
] = 0

horizontal_kernel = cv2.getStructuringElement(
    cv2.MORPH_RECT,
    (
        max(15, page_width // 90),
        3
    )
)

horizontal_mask = cv2.morphologyEx(
    purple_mask,
    cv2.MORPH_CLOSE,
    horizontal_kernel,
    iterations=2
)

vertical_kernel = cv2.getStructuringElement(
    cv2.MORPH_RECT,
    (
        3,
        max(15, page_height // 55)
    )
)

vertical_mask = cv2.morphologyEx(
    purple_mask,
    cv2.MORPH_CLOSE,
    vertical_kernel,
    iterations=2
)

connected_mask = cv2.bitwise_or(
    horizontal_mask,
    vertical_mask
)

merge_kernel = cv2.getStructuringElement(
    cv2.MORPH_RECT,
    (
        max(7, page_width // 200),
        max(7, page_height // 100)
    )
)

connected_mask = cv2.dilate(
    connected_mask,
    merge_kernel,
    iterations=2
)

cv2.imwrite(
    os.path.join(DEBUG_DIR, "purple_mask.png"),
    purple_mask
)

cv2.imwrite(
    os.path.join(DEBUG_DIR, "connected_mask.png"),
    connected_mask
)

contours, _ = cv2.findContours(
    connected_mask,
    cv2.RETR_EXTERNAL,
    cv2.CHAIN_APPROX_SIMPLE
)

candidate_boxes = []

for contour in contours:

    x, y, w, h = cv2.boundingRect(contour)

    width_ratio = w / page_width
    height_ratio = h / page_height
    aspect_ratio = w / max(h, 1)

    if (
        0.07 <= width_ratio <= 0.17
        and 0.09 <= height_ratio <= 0.30
        and 0.55 <= aspect_ratio <= 1.90
        and y > page_height * 0.35
    ):
        candidate_boxes.append(
            (x, y, w, h)
        )
def calculate_iou(box1, box2):

    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left = max(x1, x2)
    top = max(y1, y2)

    right = min(
        x1 + w1,
        x2 + w2
    )

    bottom = min(
        y1 + h1,
        y2 + h2
    )

    intersection_width = max(
        0,
        right - left
    )

    intersection_height = max(
        0,
        bottom - top
    )

    intersection_area = (
        intersection_width
        * intersection_height
    )

    area1 = w1 * h1
    area2 = w2 * h2

    union_area = (
        area1
        + area2
        - intersection_area
    )

    if union_area == 0:
        return 0

    return intersection_area / union_area


candidate_boxes = sorted(
    candidate_boxes,
    key=lambda box: box[2] * box[3],
    reverse=True
)

filtered_boxes = []

for box in candidate_boxes:

    duplicate = False

    for selected_box in filtered_boxes:

        if calculate_iou(
            box,
            selected_box
        ) > 0.35:

            duplicate = True
            break

    if not duplicate:
        filtered_boxes.append(box)

print(
    "자동 탐지된 칸 개수:",
    len(filtered_boxes)
)

if len(filtered_boxes) != 14:

    print(
        "14개가 정확히 탐지되지 않아 "
        "전체 격자 위치를 계산합니다."
    )

    grid_left = int(
        page_width * 0.047
    )

    grid_right = int(
        page_width * 0.965
    )

    grid_top = int(
        page_height * 0.455
    )

    grid_bottom = int(
        page_height * 0.910
    )

    grid_width = (
        grid_right - grid_left
    )

    grid_height = (
        grid_bottom - grid_top
    )

    cell_width = grid_width / 7
    cell_height = grid_height / 2

    filtered_boxes = []

    for row in range(2):

        for column in range(7):

            x = int(
                grid_left
                + column * cell_width
            )

            y = int(
                grid_top
                + row * cell_height
            )

            w = int(cell_width)
            h = int(cell_height)

            filtered_boxes.append(
                (x, y, w, h)
            )

filtered_boxes = sorted(
    filtered_boxes,
    key=lambda box: (
        box[1] + box[3] / 2
    )
)

first_row = sorted(
    filtered_boxes[:7],
    key=lambda box: box[0]
)

second_row = sorted(
    filtered_boxes[7:14],
    key=lambda box: box[0]
)

boxes = first_row + second_row

if len(boxes) != 14:
    raise ValueError(
        f"14개 칸을 만들지 못했습니다. "
        f"현재 개수: {len(boxes)}"
    )

detected_preview = page_image.copy()

for index, (x, y, w, h) in enumerate(boxes):

    cv2.rectangle(
        detected_preview,
        (x, y),
        (x + w, y + h),
        (0, 0, 255),
        3
    )

    cv2.putText(
        detected_preview,
        str(index + 1),
        (x + 8, y + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 255),
        2
    )

cv2.imwrite(
    os.path.join(
        DEBUG_DIR,
        "detected_boxes.png"
    ),
    detected_preview
)

def extract_handwriting(
    cell_image,
    output_size=128,
    character_size=104
):

    if (
        cell_image is None
        or cell_image.size == 0
    ):
        return np.full(
            (
                output_size,
                output_size,
                3
            ),
            255,
            dtype=np.uint8
        )

    cleaned_cell = cell_image.copy()

    cell_height, cell_width = (
        cleaned_cell.shape[:2]
    )

    cell_purple_mask = create_purple_mask(
        cleaned_cell
    )

    purple_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (5, 5)
    )

    cell_purple_mask = cv2.dilate(
        cell_purple_mask,
        purple_kernel,
        iterations=1
    )

    cleaned_cell[
        cell_purple_mask > 0
    ] = (255, 255, 255)

    handwriting_top = int(
        cell_height * 0.24
    )

    handwriting_region = cleaned_cell[
        handwriting_top:cell_height,
        :
    ].copy()

    region_height, region_width = (
        handwriting_region.shape[:2]
    )

    gray = cv2.cvtColor(
        handwriting_region,
        cv2.COLOR_BGR2GRAY
    )

    black_mask = cv2.threshold(
        gray,
        BLACK_THRESHOLD,
        255,
        cv2.THRESH_BINARY_INV
    )[1]

    remove_left_right = max(
        5,
        int(region_width * 0.08)
    )

    remove_top = max(
        5,
        int(region_height * 0.04)
    )

    remove_bottom = max(
        4,
        int(region_height * 0.03)
    )

    black_mask[
        :,
        :remove_left_right
    ] = 0

    black_mask[
        :,
        region_width - remove_left_right:
    ] = 0

    black_mask[
        :remove_top,
        :
    ] = 0

    black_mask[
        region_height - remove_bottom:,
        :
    ] = 0

    number_of_labels, labels, stats, _ = (
        cv2.connectedComponentsWithStats(
            black_mask,
            connectivity=8
        )
    )

    clean_black_mask = np.zeros_like(
        black_mask
    )

    minimum_area = max(
        12,
        int(
            region_width
            * region_height
            * 0.00035
        )
    )

    for label_number in range(
        1,
        number_of_labels
    ):

        area = stats[
            label_number,
            cv2.CC_STAT_AREA
        ]

        component_y = stats[
            label_number,
            cv2.CC_STAT_TOP
        ]

        component_height = stats[
            label_number,
            cv2.CC_STAT_HEIGHT
        ]

        if area < minimum_area:
            continue

        if (
            component_y
            < region_height * 0.08
            and component_height
            < region_height * 0.18
        ):
            continue

        clean_black_mask[
            labels == label_number
        ] = 255

    coordinates = cv2.findNonZero(
        clean_black_mask
    )

    if coordinates is None:

        crop_left = int(
            region_width * 0.12
        )

        crop_right = int(
            region_width * 0.88
        )

        crop_top = int(
            region_height * 0.08
        )

        crop_bottom = int(
            region_height * 0.95
        )

        handwriting_crop = handwriting_region[
            crop_top:crop_bottom,
            crop_left:crop_right
        ]

    else:

        x, y, w, h = cv2.boundingRect(
            coordinates
        )

        padding = max(
            12,
            int(max(w, h) * 0.20)
        )

        crop_left = max(
            0,
            x - padding
        )

        crop_top = max(
            0,
            y - padding
        )

        crop_right = min(
            region_width,
            x + w + padding
        )

        crop_bottom = min(
            region_height,
            y + h + padding
        )

        handwriting_crop = handwriting_region[
            crop_top:crop_bottom,
            crop_left:crop_right
        ]

    if handwriting_crop.size == 0:

        return np.full(
            (
                output_size,
                output_size,
                3
            ),
            255,
            dtype=np.uint8
        )

    remaining_purple = create_purple_mask(
        handwriting_crop
    )

    handwriting_crop[
        remaining_purple > 0
    ] = (255, 255, 255)

    crop_height, crop_width = (
        handwriting_crop.shape[:2]
    )

    scale = min(
        character_size / crop_width,
        character_size / crop_height
    )

    new_width = max(
        1,
        round(crop_width * scale)
    )

    new_height = max(
        1,
        round(crop_height * scale)
    )

    interpolation = (
        cv2.INTER_AREA
        if scale < 1
        else cv2.INTER_CUBIC
    )

    resized = cv2.resize(
        handwriting_crop,
        (new_width, new_height),
        interpolation=interpolation
    )
    canvas = np.full(
        (
            output_size,
            output_size,
            3
        ),
        255,
        dtype=np.uint8
    )

    start_x = (
        output_size - new_width
    ) // 2

    start_y = (
        output_size - new_height
    ) // 2

    canvas[
        start_y:start_y + new_height,
        start_x:start_x + new_width
    ] = resized

    return canvas

saved_paths = []

for (box, letter) in zip(
    boxes,
    letters
):

    x, y, w, h = box

    x1 = max(0, x)
    y1 = max(0, y)

    x2 = min(
        page_width,
        x + w
    )

    y2 = min(
        page_height,
        y + h
    )

    cell_image = page_image[
        y1:y2,
        x1:x2
    ]

    result_image = extract_handwriting(
        cell_image,
        output_size=OUTPUT_SIZE,
        character_size=CHARACTER_SIZE
    )
    save_path = os.path.join(
        OUTPUT_DIR,
        f"{letter}.png"
    )

    success = cv2.imwrite(
        save_path,
        result_image
    )

    if not success:
        raise IOError(
            f"이미지 저장 실패: {save_path}"
        )

    saved_paths.append(save_path)