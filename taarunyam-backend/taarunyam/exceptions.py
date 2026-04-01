from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Wraps all DRF error responses in our standard envelope:
    { success: false, data: {}, message: '...' }
    """
    response = exception_handler(exc, context)

    if response is not None:
        original_data = response.data
        message = ''

        if isinstance(original_data, dict):
            # Pull the first error message for the top-level message field
            for key, value in original_data.items():
                if isinstance(value, list) and len(value) > 0:
                    message = f"{key}: {value[0]}" if key != 'detail' else str(value[0])
                    break
                elif isinstance(value, str):
                    message = value
                    break
        elif isinstance(original_data, list) and len(original_data) > 0:
            message = str(original_data[0])
        elif isinstance(original_data, str):
            message = original_data

        response.data = {
            'success': False,
            'data': original_data if not isinstance(original_data, str) else {},
            'message': message or str(exc),
        }

    return response
