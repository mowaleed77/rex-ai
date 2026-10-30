
from .base import Agent, AgentResult


class CurriculumAgent(Agent):
    name = "curriculum"

    def run(self, task: dict) -> AgentResult:
        action = task.get("action", "validate")

        if action == "generate":
            return self.generate(task)

        if action == "gap_analysis":
            return self.gap_analysis(task)

        if action == "validate":
            return self.validate(task)

        return AgentResult(
            self.name,
            False,
            message="Choose action: validate, generate, or gap_analysis."
        )

    def generate(self, task: dict) -> AgentResult:
        course = task.get("course")
        level = task.get("level", "Beginner")
        outcomes = task.get("learning_outcomes")
        duration = task.get("duration_hours", 12)

        if not isinstance(course, str) or not course.strip():
            return AgentResult(
                self.name, False, message="Please provide a course title."
            )

        if not isinstance(outcomes, list) or not outcomes:
            return AgentResult(
                self.name, False,
                message="Provide learning_outcomes as a non-empty list."
            )

        if not all(isinstance(item, str) and item.strip() for item in outcomes):
            return AgentResult(
                self.name, False,
                message="Every learning outcome must be a non-empty string."
            )

        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            return AgentResult(
                self.name, False,
                message="duration_hours must be a positive number."
            )

        hours_per_module = round(duration / len(outcomes), 2)

        modules = [
            {
                "module": index,
                "title": outcome,
                "topics": [outcome],
                "duration_hours": hours_per_module,
                "activity": "Practical exercise and knowledge check"
            }
            for index, outcome in enumerate(outcomes, start=1)
        ]

        output = {
            "course": course.strip(),
            "level": level,
            "duration_hours": duration,
            "learning_outcomes": outcomes,
            "modules": modules,
            "status": "Proposed curriculum - requires expert review"
        }

        return AgentResult(
            self.name,
            True,
            output=output,
            message=f"Generated a proposed curriculum for {course}.",
            sources=[]
        )

    def gap_analysis(self, task: dict) -> AgentResult:
        required_topics = task.get("required_topics")
        curriculum = task.get("curriculum")

        if not isinstance(required_topics, list) or not required_topics:
            return AgentResult(
                self.name, False,
                message="Provide a non-empty required_topics list."
            )

        if not isinstance(curriculum, list):
            return AgentResult(
                self.name, False,
                message="Provide curriculum as a list of course objects."
            )

        actual_topics = []

        for course in curriculum:
            if not isinstance(course, dict):
                return AgentResult(
                    self.name, False,
                    message="Each curriculum item must be a course object."
                )

            topics = course.get("topics", [])

            if not isinstance(topics, list):
                return AgentResult(
                    self.name, False,
                    message="Course topics must be a list."
                )

            actual_topics.extend(
                topic.casefold().strip()
                for topic in topics
                if isinstance(topic, str)
            )

        missing_topics = [
            topic for topic in required_topics
            if isinstance(topic, str)
            and topic.casefold().strip() not in actual_topics
        ]

        output = {
            "required_topics": required_topics,
            "covered_topics": [
                topic for topic in required_topics
                if isinstance(topic, str)
                and topic.casefold().strip() in actual_topics
            ],
            "missing_topics": missing_topics,
            "coverage_percentage": round(
                100 * (len(required_topics) - len(missing_topics))
                / len(required_topics), 2
            ),
            "accreditation_status": "Not assessed"
        }

        return AgentResult(
            self.name,
            True,
            output=output,
            message=(
                f"Gap analysis complete. "
                f"Found {len(missing_topics)} missing topic(s)."
            ),
            sources=[]
        )

    def validate(self, task: dict) -> AgentResult:
        curriculum = task.get("curriculum", [])

        if not isinstance(curriculum, list) or not curriculum:
            return AgentResult(
                self.name, False,
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

        return AgentResult(
            self.name,
            True,
            output=output,
            message=(
                f"Reviewed {len(reviewed_courses)} course(s). "
                f"Found {len(issues)} issue(s). "
                "This is a curriculum structure review, not an official "
                "accreditation assessment."
            ),
            sources=[]
        )
