from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
import models, schemas, auth

router = APIRouter()

# 注册接口
@router.post("/register", response_model=schemas.UserDisplay)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. 检查用户名是否存在
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 2. 创建用户
    print(f"尝试加密的内容: {user.password}")
    print(f"内容类型: {type(user.password)}")
    print(f"内容长度: {len(user.password.encode('utf-8'))}")
    hashed_password = auth.get_password_hash(user.password[:72])
    print(11111111111111111111111111111111111111111111111111111111)
    new_user = models.User(
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# 登录接口
# 注意：这里使用 OAuth2PasswordRequestForm 是为了适配 Swagger UI 的 Authorize 按钮
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 1. 验证用户
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. 生成 Token
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# 获取当前用户信息
@router.get("/me", response_model=schemas.UserDisplay)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user