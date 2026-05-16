# [인프라] AWS S3 파일 다운로드 유틸리티
# boto3는 동기 API라 asyncio 이벤트 루프 블로킹 방지를 위해 run_in_executor로 감쌈
# prefix: 버킷 내 공통 상위 경로 (예: "pos-mk3-import-data") — 설정하면 모든 키 앞에 자동으로 붙음

import asyncio
from pathlib import Path

import boto3


class S3Client:
    def __init__(self, bucket: str, region: str, access_key_id: str, secret_access_key: str, prefix: str = ""):
        self._bucket = bucket
        # prefix가 있으면 끝에 / 붙여서 키 조합 시 편하게 사용
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""
        # boto3 클라이언트는 스레드 안전 — 여러 요청에서 공유해도 무방
        self._client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def _full_key(self, key: str) -> str:
        return self._prefix + key

    async def download_file(self, key: str, dest: Path) -> None:
        """S3 오브젝트 하나를 dest 경로로 다운로드"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._client.download_file, self._bucket, self._full_key(key), str(dest))

    async def upload_file(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> None:
        """content를 S3 오브젝트로 업로드"""
        loop = asyncio.get_running_loop()
        full_key = self._full_key(key)
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(Bucket=self._bucket, Key=full_key, Body=content, ContentType=content_type),
        )

    async def list_keys(self, prefix: str) -> list[str]:
        """prefix 하위 오브젝트 키 목록 반환 — 폴더 객체(끝이 /)는 제외, prefix 부분은 제거해서 반환"""
        loop = asyncio.get_running_loop()
        full_prefix = self._full_key(prefix)

        def _list() -> list[str]:
            response = self._client.list_objects_v2(Bucket=self._bucket, Prefix=full_prefix)
            return [
                obj["Key"][len(self._prefix):]  # 공통 prefix 제거 → import_service의 키 상수와 일치
                for obj in response.get("Contents", [])
                if not obj["Key"].endswith("/")
            ]

        return await loop.run_in_executor(None, _list)
