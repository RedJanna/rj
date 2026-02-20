"""Restaurant plan, table assignment and staff routes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel


def build_restaurant_plan_router(
    project_root: Path,
    restaurant_staff: Dict[str, Dict[str, Any]],
) -> APIRouter:
    router = APIRouter(tags=["restaurant-plan"])

    restaurant_layout_file = project_root / "data" / "restaurant_layout.json"
    restaurant_assignments_file = project_root / "data" / "restaurant_table_assignments.json"
    restaurant_layout_by_date_file = project_root / "data" / "restaurant_layout_by_date.json"
    restaurant_plan_dir = project_root / "data" / "restaurant_plans"
    restaurant_plan_main_basename = "main"

    def _ensure_data_dir():
        (project_root / "data").mkdir(parents=True, exist_ok=True)

    def _read_json(path: Path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def _write_json(path: Path, payload) -> None:
        _ensure_data_dir()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    class RestaurantTable(BaseModel):
        table_id: str
        x_cm: float
        y_cm: float
        seats: int = 4
        size_cm: Optional[int] = None

    class RestaurantLayout(BaseModel):
        plan_width_cm: int = 1738
        plan_height_cm: int = 975
        table_size_cm: int = 80
        tables: List[RestaurantTable] = []

    class AssignTableRequest(BaseModel):
        date: str
        table_id: str
        reservation_id: int
        ends_at: Optional[str] = None

    class UnassignTableRequest(BaseModel):
        date: str
        reservation_id: int

    class RestaurantPlanSaveRequest(BaseModel):
        svg: str
        date: str | None = None
        scope: str = "date"

    @router.get("/admin/restaurant-staff")
    async def get_restaurant_staff():
        return restaurant_staff

    @router.post("/admin/restaurant-staff/{staff_id}/phone")
    async def update_staff_phone(staff_id: str, phone: str):
        if staff_id in restaurant_staff:
            restaurant_staff[staff_id]["phone"] = phone
            return {"status": "ok", "message": f"{restaurant_staff[staff_id]['name']} telefonu güncellendi"}
        return {"error": "Personel bulunamadı"}

    @router.get("/admin/restaurant/layout")
    async def get_restaurant_layout():
        default = RestaurantLayout().model_dump()
        payload = _read_json(restaurant_layout_file, default)
        payload.setdefault("plan_width_cm", 1738)
        payload.setdefault("plan_height_cm", 975)
        payload.setdefault("table_size_cm", 80)
        payload.setdefault("tables", [])
        return payload

    @router.post("/admin/restaurant/layout")
    async def save_restaurant_layout(layout: RestaurantLayout):
        _write_json(restaurant_layout_file, layout.model_dump())
        return {"status": "ok"}

    @router.delete("/admin/restaurant/layout")
    async def delete_restaurant_layout(date: str):
        overrides = _read_json(restaurant_layout_by_date_file, {"by_date": {}})
        if not isinstance(overrides, dict):
            overrides = {"by_date": {}}
        overrides.setdefault("by_date", {})
        overrides["by_date"].pop(date, None)
        _write_json(restaurant_layout_by_date_file, overrides)
        return {"ok": True, "deleted_date": date}

    @router.get("/admin/restaurant/assignments")
    async def get_table_assignments(date: str):
        payload = _read_json(restaurant_assignments_file, {"dates": {}})
        day = (payload.get("dates") or {}).get(date, {})
        return {"status": "ok", "date": date, "assignments": day}

    @router.post("/admin/restaurant/assign")
    async def assign_reservation_to_table(req: AssignTableRequest):
        payload = _read_json(restaurant_assignments_file, {"dates": {}})
        dates = payload.setdefault("dates", {})
        day = dates.setdefault(req.date, {})
        for t_id, a in list(day.items()):
            if a and int(a.get("reservation_id")) == int(req.reservation_id):
                day.pop(t_id, None)
        day[req.table_id] = {"reservation_id": int(req.reservation_id), "ends_at": req.ends_at}
        _write_json(restaurant_assignments_file, payload)
        return {"status": "ok"}

    @router.post("/admin/restaurant/unassign")
    async def unassign_reservation(req: UnassignTableRequest):
        payload = _read_json(restaurant_assignments_file, {"dates": {}})
        day = (payload.get("dates") or {}).get(req.date, {})
        removed = False
        for t_id, a in list(day.items()):
            if a and int(a.get("reservation_id")) == int(req.reservation_id):
                day.pop(t_id, None)
                removed = True
        _write_json(restaurant_assignments_file, payload)
        return {"status": "ok", "removed": removed}

    @router.get("/admin/restaurant/plan-image")
    async def restaurant_plan_image():
        static_dir = project_root / "static"
        custom_candidates = [
            static_dir / "restaurant_plan_custom.svg",
            static_dir / "restaurant_plan_custom.png",
            static_dir / "restaurant_plan_custom.jpg",
            static_dir / "restaurant_plan_custom.jpeg",
            static_dir / "restaurant_plan_custom.webp",
        ]
        custom = next((p for p in custom_candidates if p.exists()), None)
        if custom:
            suf = custom.suffix.lower()
            mt = {
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".webp": "image/webp",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
            }.get(suf, "application/octet-stream")
            return FileResponse(str(custom), media_type=mt, headers={"Cache-Control": "no-store"})

        candidates = [
            static_dir / "restaurant_plan.pdf",
            project_root / "restoran planı.pdf",
            project_root / "restoran_plani.pdf",
        ]
        pdf_path = next((p for p in candidates if p.exists()), None)
        if not pdf_path:
            raise HTTPException(status_code=404, detail="Plan dosyası bulunamadı.")

        try:
            import fitz
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PyMuPDF import hatası: {e}")

        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            rects = []
            td = page.get_text("dict")
            for b in td.get("blocks", []):
                bb = b.get("bbox")
                if bb:
                    r = fitz.Rect(bb)
                    if r.get_area() > 10:
                        rects.append(r)
            for d in page.get_drawings():
                r = d.get("rect")
                if r:
                    rr = fitz.Rect(r)
                    if rr.get_area() > 10:
                        rects.append(rr)
            if rects:
                x0 = min(r.x0 for r in rects)
                y0 = min(r.y0 for r in rects)
                x1 = max(r.x1 for r in rects)
                y1 = max(r.y1 for r in rects)
                clip = fitz.Rect(x0, y0, x1, y1)
                clip = (fitz.Rect(clip.x0 - 12, clip.y0 - 12, clip.x1 + 12, clip.y1 + 12) & page.rect)
            else:
                clip = page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip, alpha=False)
            png_bytes = pix.tobytes("png")
            doc.close()
            return Response(content=png_bytes, media_type="image/png", headers={"Cache-Control": "no-store"})
        except Exception as e:
            try:
                doc.close()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Plan render hatası: {e}")

    @router.get("/admin/restaurant/plan-svg")
    async def restaurant_plan_svg(date: str | None = None):
        by_date_dir = restaurant_plan_dir / "by_date"

        def _read_svg(p: Path) -> str | None:
            try:
                if p.exists():
                    return p.read_text(encoding="utf-8")
            except Exception:
                return None
            return None

        if date:
            s = _read_svg(by_date_dir / f"{date}.svg")
            if s is not None:
                return Response(content=s, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})

        s = _read_svg(restaurant_plan_dir / f"{restaurant_plan_main_basename}.svg")
        if s is not None:
            return Response(content=s, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
        raise HTTPException(status_code=404, detail="SVG plan bulunamadı.")

    @router.post("/admin/restaurant/plan-save")
    async def restaurant_plan_save(req: RestaurantPlanSaveRequest):
        by_date_dir = restaurant_plan_dir / "by_date"
        by_date_dir.mkdir(parents=True, exist_ok=True)
        scope = (req.scope or "date").lower().strip()
        if scope == "main" or not req.date:
            target = restaurant_plan_dir / f"{restaurant_plan_main_basename}.svg"
        else:
            safe_date = re.sub(r"[^0-9\-]", "", req.date)
            target = by_date_dir / f"{safe_date}.svg"
        try:
            target.write_text(req.svg, encoding="utf-8")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"SVG kaydedilemedi: {e}")
        return {"ok": True, "saved_to": str(target), "scope": scope, "date": req.date}

    return router
