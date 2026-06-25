"""
mock_market 管理 API —— 查看和修改模拟公司及其超参数。
前缀 /api/admin，无需认证（本地/开发使用）。
"""

from fastapi import APIRouter, HTTPException

from mock_market.engine import MockPriceEngine
from mock_market.schemas import (
    MockCompanyCreate, MockCompanyUpdate,
    MockCompanyDisplay, MockCompanyList,
)
from mock_market.service import (
    get_all_companies, get_company_by_code,
    create_company, update_company, delete_company,
    get_company_bar_count,
)

router = APIRouter()


@router.get("/companies", response_model=MockCompanyList)
def list_companies():
    """列出所有模拟公司及其配置。"""
    companies = get_all_companies()
    return MockCompanyList(
        companies=[MockCompanyDisplay.model_validate(c) for c in companies],
        total=len(companies),
    )


@router.get("/companies/{code}", response_model=MockCompanyDisplay)
def get_company(code: str):
    """获取单家公司详情。"""
    c = get_company_by_code(code)
    if c is None:
        raise HTTPException(status_code=404, detail=f"公司 {code} 不存在")
    return MockCompanyDisplay.model_validate(c)


@router.post("/companies", response_model=MockCompanyDisplay, status_code=201)
async def create_new_company(data: MockCompanyCreate):
    """创建新的模拟公司，并通知引擎开始生成价格。"""
    if get_company_by_code(data.code) is not None:
        raise HTTPException(status_code=409, detail=f"公司 {data.code} 已存在")

    c = create_company(data.model_dump())
    engine = MockPriceEngine.get_instance()
    await engine.add_company(data.code)
    return MockCompanyDisplay.model_validate(c)


@router.put("/companies/{code}", response_model=MockCompanyDisplay)
async def update_company_params(code: str, data: MockCompanyUpdate):
    """更新公司超参数（部分更新），引擎实时生效。"""
    c = update_company(code, data.model_dump(exclude_unset=True))
    if c is None:
        raise HTTPException(status_code=404, detail=f"公司 {code} 不存在")

    engine = MockPriceEngine.get_instance()
    await engine.reload_company(code)
    return MockCompanyDisplay.model_validate(c)


@router.delete("/companies/{code}")
async def deactivate_company(code: str):
    """停用公司（软删除），停止为该代码生成价格。"""
    if not delete_company(code):
        raise HTTPException(status_code=404, detail=f"公司 {code} 不存在")

    engine = MockPriceEngine.get_instance()
    await engine.reload_company(code)
    return {"detail": f"公司 {code} 已停用"}


@router.post("/companies/{code}/reset")
async def reset_company(code: str):
    """重置公司：清除所有历史 K 线，价格回到 initial_price 重新开始。"""
    c = get_company_by_code(code)
    if c is None:
        raise HTTPException(status_code=404, detail=f"公司 {code} 不存在")

    bar_count = get_company_bar_count(code)
    engine = MockPriceEngine.get_instance()
    await engine.reset_company(code)
    return {
        "detail": f"公司 {code} 已重置",
        "deleted_bars": bar_count,
    }
