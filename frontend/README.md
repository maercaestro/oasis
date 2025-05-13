# OASIS

OASIS is a scheduling system designed to optimize vessel cargo processing, inventory updates, and grade-based visualization. This project includes both backend and frontend components to manage and display scheduling data effectively.

## Features

### Backend
- Processes vessel cargo and updates inventory using `FeedstockParcel` objects.
- Provides an API endpoint (`/api/scheduler/run`) to run the scheduling logic.
- Ensures compatibility between vessel cargo grades and recipes.

### Frontend
- Displays grade-based processing data in a daily plan chart.
- Allows users to edit schedules and visualize grade consumption.

## Installation

### Prerequisites
- Node.js and npm
- Python 3.10+

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/maercaestro/oasis.git
   cd oasis
   ```

2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Install frontend dependencies:
   ```bash
   cd ../frontend
   npm install
   ```

4. Start the backend server:
   ```bash
   cd ../backend
   python api.py
   ```

5. Start the frontend development server:
   ```bash
   cd ../frontend
   npm run dev
   ```

## Testing

### Backend
- Run tests for the scheduler logic:
  ```bash
  pytest test_scheduler.py
  ```

- Validate the API endpoint:
  ```bash
  pytest test_api_scheduler.py
  ```

### Frontend
- Ensure the grade-based visualization works as expected by running the development server and interacting with the UI.

## Documentation

- Backend logic is documented in `scheduler.py` and `api.py`.
- Frontend components are documented in their respective files under `src/components/`.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.
