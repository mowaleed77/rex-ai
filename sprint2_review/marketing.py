
from .base import Agent, AgentResult


class MarketingAgent(Agent):
    name = "marketing"

    def run(self, task: dict) -> AgentResult:
        course = task.get("course", {})
        title = course.get("title", "").strip()

        if not title:
            return AgentResult(
                agent=self.name,
                ok=False,
                message="Course title is required."
            )

        audience = task.get(
            "target_audience",
            "students interested in developing new skills"
        )

        channels = task.get(
            "channels",
            ["instagram", "facebook", "linkedin", "email", "whatsapp"]
        )

        variations = max(1, min(int(task.get("variations", 2)), 5))

        description = course.get("description", "")
        price = course.get("price")
        duration = course.get("duration_hours")
        promotion = course.get("promotion")

        details = []
        if description:
            details.append(description)
        if duration:
            details.append(f"Duration: {duration} hours")
        if price:
            details.append(f"Price: {price}")
        if promotion:
            details.append(f"Offer: {promotion}")

        course_details = " ".join(details)

        templates = {
            "instagram": (
                f"Ready to learn something new? Join {title}! "
                f"Designed for {audience}. {course_details}"
            ),
            "facebook": (
                f"Discover {title} and take the next step in your learning journey. "
                f"Suitable for {audience}. {course_details}"
            ),
            "linkedin": (
                f"Develop your skills with {title}. "
                f"This learning opportunity is designed for {audience}. "
                f"{course_details}"
            ),
            "email": (
                f"Subject: Explore {title}\n\n"
                f"Hello,\nDiscover {title}, designed for {audience}. "
                f"{course_details}\n\n"
                "Contact our team to learn more."
            ),
            "whatsapp": (
                f"Hello! Interested in {title}? "
                f"This course is designed for {audience}. "
                f"{course_details} Contact us for more information."
            ),
        }

        content = {}

        for channel in channels:
            channel = channel.lower().strip()

            if channel not in templates:
                continue

            content[channel] = []

            for number in range(1, variations + 1):
                message = templates[channel]

                if number == 2:
                    message = (
                        f"Start your learning journey with {title}! "
                        f"Explore the course designed for {audience}. "
                        f"{course_details}"
                    )
                elif number >= 3:
                    message = (
                        f"Take the next step toward your learning goals "
                        f"with {title}. {course_details}"
                    )

                content[channel].append({
                    "variation": number,
                    "text": message.strip(),
                    "headline": f"Explore {title}",
                    "call_to_action": "Contact us to learn more."
                })

        output = {
            "course_title": title,
            "target_audience": audience,
            "content": content,
            "campaign_strategy": {
                "goal": "Increase course awareness and inquiries",
                "target_audience": audience,
                "recommended_action": "Share content on the selected channels"
            },
            "status": "pending_admin_approval",
            "approved": False,
            "published": False
        }

        return AgentResult(
            agent=self.name,
            ok=True,
            output=output,
            message="Marketing content generated. Admin approval is required before publishing."
        )
