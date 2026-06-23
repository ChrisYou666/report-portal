from __future__ import annotations

from pathlib import Path

import requests

from app.core.config import settings
from app.models import UploadBatch
from app.services.onedrive import OneDriveUploadError, upload_report_to_onedrive
from app.services.report_generator import HARVEST_REPORT_NAME, get_generated_report_image_paths


def push_batch_report(batch: UploadBatch) -> str:
    messages: list[str] = []

    if settings.teams_webhook_url:
        messages.append(push_to_teams(batch))

    if settings.whatsapp_access_token and settings.whatsapp_phone_number_id and settings.whatsapp_to:
        messages.append(push_to_whatsapp(batch))

    if not messages:
        batch.status = "push_skipped"
        return "推送已触发，但未配置 Teams 或 WhatsApp 参数，暂未外发。"

    batch.status = "pushed"
    return "；".join(messages)


def push_to_teams(batch: UploadBatch) -> str:
    report_links, upload_errors = upload_generated_reports(batch)
    link_text = "\n".join(f"- [{name}图片]({web_url})" for name, web_url, _ in report_links)
    if not link_text:
        link_text = "- 未找到已生成的产量监控图片，请先生成报表。"
    error_text = "\n".join(f"- {message}" for message in upload_errors)
    if error_text:
        error_text = f"\n\n**上传提醒**\n{error_text}"

    message = (
        f"**{HARVEST_REPORT_NAME}已生成**\n\n"
        f"- 统计日期：{batch.report_date}\n"
        f"- 园区/工厂：{batch.site or '-'}\n"
        f"- 批次号：{batch.batch_no}\n\n"
        f"**图片报表**\n{link_text}"
        f"{error_text}"
    )
    payload = build_teams_payload(batch, report_links, upload_errors, message)
    response = requests.post(settings.teams_webhook_url, json=payload, timeout=15)
    response.raise_for_status()
    return "已触发 Teams 推送"


def build_teams_payload(
    batch: UploadBatch,
    report_links: list[tuple[str, str, str]],
    upload_errors: list[str],
    message: str,
) -> dict:
    card_body = [
        {
            "type": "TextBlock",
            "text": HARVEST_REPORT_NAME,
            "weight": "Bolder",
            "size": "Large",
            "wrap": True,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "统计日期", "value": str(batch.report_date)},
                {"title": "园区/工厂", "value": batch.site or "-"},
                {"title": "批次号", "value": batch.batch_no},
            ],
        },
    ]
    for name, web_url, image_url in report_links:
        if image_url:
            card_body.append(
                {
                    "type": "Image",
                    "url": image_url,
                    "altText": name,
                    "size": "Stretch",
                    "selectAction": {
                        "type": "Action.OpenUrl",
                        "url": web_url,
                    },
                }
            )
        card_body.append(
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": f"打开查看{name}",
                        "url": web_url,
                    }
                ],
            }
        )
    if upload_errors:
        card_body.append(
            {
                "type": "TextBlock",
                "text": "上传提醒：\n" + "\n".join(upload_errors),
                "wrap": True,
                "color": "Warning",
            }
        )

    return {
        "text": message,
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": card_body,
                },
            }
        ],
    }


def upload_generated_reports(batch: UploadBatch) -> tuple[list[tuple[str, str, str]], list[str]]:
    links: list[tuple[str, str, str]] = []
    errors: list[str] = []
    for report_name, local_path in get_generated_report_image_paths(batch).items():
        if not local_path.exists():
            errors.append(f"{report_name} 本地报表不存在：{local_path}")
            continue
        try:
            result = upload_report_to_onedrive(
                local_path=str(local_path),
                filename=Path(local_path).name,
                batch_no=batch.batch_no,
                report_date=batch.report_date,
                site=batch.site,
                report_name=report_name,
            )
        except OneDriveUploadError as exc:
            errors.append(f"{report_name} 上传到 SharePoint 失败：{exc}")
            continue
        links.append((report_name, result.web_url or result.cloud_path, result.download_url or result.web_url))
    return links, errors


def push_to_whatsapp(batch: UploadBatch) -> str:
    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": settings.whatsapp_to,
        "type": "text",
        "text": {
            "body": f"{HARVEST_REPORT_NAME}已生成：{batch.report_name}\n批次号：{batch.batch_no}\n日期：{batch.report_date}"
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return "已推送到 WhatsApp"
