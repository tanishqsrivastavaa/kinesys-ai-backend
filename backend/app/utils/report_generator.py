from typing import Dict, List, Any
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from uuid import UUID
import textstat
import re
from jinja2 import Template
import weasyprint
from io import BytesIO

from app.models.draft_model import Draft
from app.models.comment_model import Comment

async def generate_draft_report_data(db: AsyncSession, draft_id: UUID, user_id: UUID) -> Dict[str, Any]:
    """Generate report data for a draft"""
    
    # Get draft
    result = await db.exec(
        select(Draft).where(Draft.id == draft_id, Draft.user_id == user_id)
    )
    draft = result.first()
    if not draft:
        raise ValueError("Draft not found")

    # Get comments
    comments_result = await db.exec(
        select(Comment).where(Comment.draft_id == draft_id)
    )
    comments = comments_result.all()

    return {
        "draft_info": {
            "id": str(draft.id),
            "title": draft.summary or "Untitled Draft",
            "created_date": draft.created_at.strftime("%Y-%m-%d %H:%M"),
        },
        "overall_sentiment": _calculate_overall_sentiment(comments),
        "comment_count": len(comments),
        "draft_length": _calculate_draft_length(draft.draft),
        "readability_score": _calculate_readability_score(draft.draft),
        "feedback_ratio": _calculate_feedback_ratio(comments),
        "actionable_insights": _generate_actionable_insights(comments, draft),
    }

def _calculate_overall_sentiment(comments: List[Comment]) -> Dict[str, Any]:
    """Calculate overall sentiment metrics"""
    if not comments:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0}

    scores = []
    for comment in comments:
        try:
            # Check if comment has sentiment_score attribute and handle it safely
            if hasattr(comment, 'sentiment_score') and comment.sentiment_score is not None:
                score = float(comment.sentiment_score)
                # If score is between 0-1, convert to -1 to 1
                if 0 <= score <= 1:
                    normalized_score = (score - 0.5) * 2
                else:
                    normalized_score = score
                scores.append(normalized_score)
            else:
                scores.append(0.0)
        except (ValueError, TypeError):
            scores.append(0.0)

    if not scores:
        return {"score": 0.0, "label": "neutral", "confidence": 0.0}

    avg_score = sum(scores) / len(scores)
    variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if len(scores) > 1 else 0
    confidence = max(0, 1 - variance)

    if avg_score > 0.1:
        label = "positive"
    elif avg_score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return {
        "score": round(avg_score, 3),
        "label": label,
        "confidence": round(confidence, 3)
    }

def _calculate_draft_length(draft_content: str) -> Dict[str, int]:
    """Calculate draft length metrics"""
    if not draft_content:
        return {"words": 0, "characters": 0, "sentences": 0, "avg_words_per_sentence": 0}
        
    words = len(draft_content.split())
    characters = len(draft_content)
    sentences = len([s for s in re.split(r'[.!?]+', draft_content.strip()) if s.strip()])
    
    return {
        "words": words,
        "characters": characters,
        "sentences": max(sentences, 1),
        "avg_words_per_sentence": round(words / max(sentences, 1), 1)
    }

def _calculate_readability_score(draft_content: str) -> Dict[str, Any]:
    """Calculate readability using Flesch Reading Ease"""
    if not draft_content or len(draft_content.strip()) < 10:
        return {"score": 50.0, "level": "standard", "grade_level": 8.0}
        
    try:
        flesch_score = textstat.flesch_reading_ease(draft_content)
        
        if flesch_score >= 90:
            level = "very-easy"
        elif flesch_score >= 80:
            level = "easy"
        elif flesch_score >= 70:
            level = "fairly-easy"
        elif flesch_score >= 60:
            level = "standard"
        elif flesch_score >= 50:
            level = "fairly-difficult"
        elif flesch_score >= 30:
            level = "difficult"
        else:
            level = "very-difficult"

        return {
            "score": round(flesch_score, 1),
            "level": level,
            "grade_level": round(textstat.flesch_kincaid_grade(draft_content), 1)
        }
    except Exception as e:
        return {"score": 50.0, "level": "standard", "grade_level": 8.0}

def _calculate_feedback_ratio(comments: List[Comment]) -> Dict[str, Any]:
    """Calculate critical vs supportive feedback ratio"""
    if not comments:
        return {
            "critical": 0, 
            "supportive": 0, 
            "neutral": 0, 
            "ratio": "N/A",
            "critical_percentage": 0.0,
            "supportive_percentage": 0.0
        }

    critical = supportive = neutral = 0
    
    for comment in comments:
        try:
            # Check different possible field names for sentiment
            sentiment_value = None
            
            if hasattr(comment, 'sentiment_label') and comment.sentiment_label:
                sentiment_value = comment.sentiment_label.lower()
            elif hasattr(comment, 'sentiment_analysis') and comment.sentiment_analysis:
                sentiment_value = comment.sentiment_analysis.lower()
            elif hasattr(comment, 'sentiment') and comment.sentiment:
                sentiment_value = comment.sentiment.lower()
            elif hasattr(comment, 'sentiment_score') and comment.sentiment_score is not None:
                # If only score available, derive label from score
                score = float(comment.sentiment_score)
                if 0 <= score <= 1:  # Assuming 0-1 scale
                    if score > 0.6:
                        sentiment_value = "positive"
                    elif score < 0.4:
                        sentiment_value = "negative"
                    else:
                        sentiment_value = "neutral"
                else:  # Assuming -1 to 1 scale
                    if score > 0.1:
                        sentiment_value = "positive"
                    elif score < -0.1:
                        sentiment_value = "negative"
                    else:
                        sentiment_value = "neutral"
            
            # Categorize based on sentiment value
            if sentiment_value:
                if sentiment_value in ["negative", "critical", "bad"]:
                    critical += 1
                elif sentiment_value in ["positive", "supportive", "good"]:
                    supportive += 1
                else:
                    neutral += 1
            else:
                neutral += 1
                
        except (ValueError, TypeError, AttributeError) as e:
            # If any error occurs, count as neutral
            neutral += 1

    total = len(comments)
    
    # Calculate ratio string
    if critical > 0 and supportive > 0:
        ratio = f"{supportive}:{critical}"
    elif supportive > 0:
        ratio = "All Supportive"
    elif critical > 0:
        ratio = "All Critical"
    else:
        ratio = "All Neutral"

    return {
        "critical": critical,
        "supportive": supportive,
        "neutral": neutral,
        "ratio": ratio,
        "critical_percentage": round((critical / total) * 100, 1) if total > 0 else 0.0,
        "supportive_percentage": round((supportive / total) * 100, 1) if total > 0 else 0.0
    }

def _generate_actionable_insights(comments: List[Comment], draft: Draft) -> List[str]:
    """Generate actionable insights"""
    insights = []
    
    if not comments:
        insights.append("📝 No feedback yet - consider sharing your draft with more reviewers")
        return insights

    try:
        sentiment_data = _calculate_overall_sentiment(comments)
        feedback_ratio = _calculate_feedback_ratio(comments)
        draft_length = _calculate_draft_length(draft.draft)

        # Sentiment insights
        if sentiment_data["score"] < -0.3:
            insights.append("⚠️ Strong negative sentiment detected - review and address major concerns")
        elif sentiment_data["score"] < -0.1:
            insights.append("📋 Mixed feedback - analyze critical comments for improvement areas")
        elif sentiment_data["score"] > 0.3:
            insights.append("✅ Excellent reception! Consider finalizing the draft")

        # Feedback ratio insights
        if feedback_ratio["critical"] > feedback_ratio["supportive"] * 2:
            insights.append("🔍 High critical feedback - prioritize addressing recurring concerns")
        elif feedback_ratio["supportive"] > feedback_ratio["critical"] * 3:
            insights.append("🎯 Strong positive reception - ready for next phase")

        # Engagement insights
        if len(comments) < 3:
            insights.append("👥 Seek more reviewers for comprehensive feedback")
        elif len(comments) > 20:
            insights.append("📊 Rich feedback collected - analyze patterns for improvements")

        # Length insights
        if draft_length["words"] < 100:
            insights.append("📏 Consider adding more detailed content and examples")
        elif draft_length["words"] > 2000:
            insights.append("✂️ Consider breaking into sections for better readability")

    except Exception as e:
        insights.append("📊 Basic analysis completed - data processing had some limitations")

    return insights[:4] if insights else ["📝 Analysis completed successfully"]

# HTML Template and PDF generation (keeping existing template)
def generate_html_report(report_data: Dict[str, Any]) -> str:
    """Generate HTML report from data"""
    template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Draft Analysis Report</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; border-bottom: 3px solid #007acc; padding-bottom: 20px; margin-bottom: 30px; }
        .title { color: #007acc; font-size: 24px; font-weight: bold; margin: 0; }
        .subtitle { color: #666; font-size: 14px; margin: 5px 0 0 0; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }
        .metric-card { background: #f8f9fa; padding: 20px; border-radius: 6px; border-left: 4px solid #007acc; }
        .metric-value { font-size: 28px; font-weight: bold; color: #007acc; margin: 0; }
        .metric-label { color: #666; font-size: 14px; margin: 5px 0 0 0; }
        .sentiment-positive { color: #28a745; }
        .sentiment-negative { color: #dc3545; }
        .sentiment-neutral { color: #ffc107; }
        .section { margin: 30px 0; }
        .section-title { font-size: 18px; color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-bottom: 15px; }
        .insights-list { list-style: none; padding: 0; }
        .insights-list li { background: #e3f2fd; padding: 12px; margin: 8px 0; border-radius: 4px; border-left: 4px solid #2196f3; }
        .feedback-bar { background: #eee; height: 20px; border-radius: 10px; overflow: hidden; margin: 10px 0; position: relative; }
        .feedback-supportive { background: #28a745; height: 100%; position: absolute; left: 0; }
        .feedback-critical { background: #dc3545; height: 100%; position: absolute; right: 0; }
        .stats-row { display: flex; justify-content: space-between; margin: 10px 0; }
        .readability-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; color: white; font-size: 12px; font-weight: bold; }
        .readability-easy { background: #28a745; }
        .readability-standard { background: #ffc107; color: #333; }
        .readability-difficult { background: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">Draft Analysis Report</h1>
            <p class="subtitle">{{ draft_info.title }} • Generated on {{ draft_info.created_date }}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <p class="metric-value sentiment-{{ overall_sentiment.label }}">{{ overall_sentiment.score }}</p>
                <p class="metric-label">Overall Sentiment Score</p>
                <small>{{ overall_sentiment.label.title() }} ({{ (overall_sentiment.confidence * 100)|round(1) }}% confidence)</small>
            </div>
            
            <div class="metric-card">
                <p class="metric-value">{{ comment_count }}</p>
                <p class="metric-label">Total Comments</p>
            </div>
            
            <div class="metric-card">
                <p class="metric-value">{{ draft_length.words }}</p>
                <p class="metric-label">Draft Length (Words)</p>
                <small>{{ draft_length.sentences }} sentences</small>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📖 Readability Analysis</h2>
            <div class="stats-row">
                <span>Flesch Reading Ease: <strong>{{ readability_score.score }}</strong></span>
                <span class="readability-badge readability-{{ readability_score.level }}">{{ readability_score.level.replace('-', ' ').title() }}</span>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">💬 Feedback Analysis</h2>
            <div class="feedback-bar">
                <div class="feedback-supportive" style="width: {{ feedback_ratio.supportive_percentage }}%"></div>
                <div class="feedback-critical" style="width: {{ feedback_ratio.critical_percentage }}%"></div>
            </div>
            <div class="stats-row">
                <span>✅ Supportive: {{ feedback_ratio.supportive }} ({{ feedback_ratio.supportive_percentage }}%)</span>
                <span>❌ Critical: {{ feedback_ratio.critical }} ({{ feedback_ratio.critical_percentage }}%)</span>
            </div>
            <p><strong>Ratio:</strong> {{ feedback_ratio.ratio }}</p>
        </div>

        <div class="section">
            <h2 class="section-title">💡 Actionable Insights</h2>
            <ul class="insights-list">
                {% for insight in actionable_insights %}
                <li>{{ insight }}</li>
                {% endfor %}
            </ul>
        </div>
    </div>
</body>
</html>
    """
    
    template = Template(template_str)
    return template.render(**report_data)

def html_to_pdf(html_content: str) -> bytes:
    """Convert HTML to PDF"""
    try:
        pdf_file = BytesIO()
        weasyprint.HTML(string=html_content).write_pdf(pdf_file)
        pdf_file.seek(0)
        return pdf_file.read()
    except Exception as e:
        raise Exception(f"PDF generation failed: {str(e)}")