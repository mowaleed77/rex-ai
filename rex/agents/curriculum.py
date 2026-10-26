
from .base import Agent, AgentResult


class CurriculumAgent(Agent):
    name = "curriculum"

    def run(self, task: dict) -> AgentResult:
        curriculum = task.get("curriculum", [])

        if not isinstance(curriculum, list) or not curriculum:
            return AgentResult(
                self.name,
                False,
                message="Please provide a non-empty curriculum list."
            )

        required_fields = ["course", "topics"]
        issues = []
        reviewed_courses = []

        for index, course in enumerate(curriculum, start=1):
            if not isinstance(course, dict):
                issues.append(f"Item {index} must be a course object.")
                continue

            missing_fields = [
                field for field in required_fields
                if field not in course
            ]

            if missing_fields:
                issues.append(
                    f"Item {index} is missing: {', '.join(missing_fields)}."
                )
                continue

            topics = course["topics"]

            if not isinstance(topics, list):
                issues.append(
                    f"{course['course']}: topics must be a list."
                )
                continue

            if not topics:
                issues.append(
                    f"{course['course']}: no topics have been provided."
                )

            reviewed_courses.append({
                "course": course["course"],
                "topic_count": len(topics),
                "topics": topics
            })

        output = {
            "reviewed_courses": reviewed_courses,
            "issues": issues,
            "course_count": len(reviewed_courses),
            "accreditation_status": "Not assessed"
        }

        message = (
            f"Reviewed {len(reviewed_courses)} course(s). "
            f"Found {len(issues)} issue(s). "
            "This is a curriculum structure review, not an official "
            "accreditation assessment."
        )

        return AgentResult(
            self.name,
            True,
            output=output,
            message=message,
            sources=[]
        )
