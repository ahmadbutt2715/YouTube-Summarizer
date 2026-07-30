import json
from dataclasses import asdict

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from . import agents


def index(request):
    return render(request, "chatapp/index.html")


@require_POST
def load_video(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request body."}, status=400)

    video_url = (payload.get("video_url") or "").strip()
    if not video_url:
        return JsonResponse({"error": "Please paste a YouTube video link."}, status=400)


    try:
        video_content = agents.load_video(video_url)
    except Exception as exc:  # noqa: BLE001 - surface any agent error to the UI
        return JsonResponse({"error": str(exc)}, status=400)


    # Reset chat state for the newly loaded video.
    request.session["video_id"] = video_content.video_id
    request.session["history"] = []

    return JsonResponse(
        {
            "video_id": video_content.video_id,
            "title": video_content.title,
            "summary": video_content.summary,
        }
    )


@require_POST
def ask_question(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request body."}, status=400)

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "Type a question first."}, status=400)

    video_id = request.session.get("video_id")
    if not video_id:
        return JsonResponse({"error": "Load a video before asking questions."}, status=400)

    history = request.session.get("history", [])

    try:
        answer = agents.ask_question(question, history)
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=400)

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    request.session["history"] = history

    return JsonResponse({"answer": answer})
