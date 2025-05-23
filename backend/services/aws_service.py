import os
import boto3
import json
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class AWSService:
    """Handles all AWS service interactions"""
    
    def __init__(self):
        self.region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.s3_bucket = os.getenv('S3_BUCKET_NAME')
        
        # Initialize AWS clients
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.rekognition_client = boto3.client('rekognition', region_name=self.region)
        self.transcribe_client = boto3.client('transcribe', region_name=self.region)
        self.comprehend_client = boto3.client('comprehend', region_name=self.region)
    
    # S3 Operations
    def upload_video_to_s3(self, file_path: str, s3_key: str) -> str:
        """
        Upload video file to S3 bucket
        
        Args:
            file_path: Local path to video file
            s3_key: S3 object key (path in bucket)
            
        Returns:
            S3 URL of uploaded file
        """
        try:
            self.s3_client.upload_file(
                file_path, 
                self.s3_bucket, 
                s3_key,
                ExtraArgs={'ContentType': 'video/mp4'}
            )
            
            # Generate URL
            url = f"https://{self.s3_bucket}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"Successfully uploaded video to S3: {url}")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to upload video to S3: {str(e)}")
            raise
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate presigned URL for secure video access"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise
    
    def delete_video_from_s3(self, s3_key: str) -> bool:
        """Delete video from S3"""
        try:
            self.s3_client.delete_object(Bucket=self.s3_bucket, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete video from S3: {str(e)}")
            return False
    
    # Rekognition Operations
    def analyze_video_labels(self, s3_key: str) -> Dict:
        """
        Detect objects and scenes in video using Rekognition
        
        Returns:
            Dictionary with detected labels and timestamps
        """
        try:
            response = self.rekognition_client.start_label_detection(
                Video={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                },
                MinConfidence=70,
                Features=['GENERAL_LABELS']
            )
            
            job_id = response['JobId']
            logger.info(f"Started Rekognition label detection job: {job_id}")
            
            # Return job ID for status checking
            return {'job_id': job_id, 'type': 'label_detection'}
            
        except ClientError as e:
            logger.error(f"Failed to start Rekognition analysis: {str(e)}")
            raise
    
    def get_label_detection_results(self, job_id: str) -> Dict:
        """Get results from Rekognition label detection job"""
        try:
            response = self.rekognition_client.get_label_detection(JobId=job_id)
            
            if response['JobStatus'] == 'SUCCEEDED':
                # Process and structure the results
                labels = {}
                for label in response.get('Labels', []):
                    label_name = label['Label']['Name']
                    confidence = label['Label']['Confidence']
                    
                    if label_name not in labels:
                        labels[label_name] = {
                            'confidence': confidence,
                            'instances': []
                        }
                    
                    if 'Timestamp' in label:
                        labels[label_name]['instances'].append({
                            'timestamp': label['Timestamp'],
                            'confidence': confidence
                        })
                
                return {
                    'status': 'completed',
                    'labels': labels,
                    'video_metadata': response.get('VideoMetadata', {})
                }
            
            return {'status': response['JobStatus']}
            
        except ClientError as e:
            logger.error(f"Failed to get Rekognition results: {str(e)}")
            raise
    
    def detect_faces_in_video(self, s3_key: str) -> Dict:
        """Start face detection job"""
        try:
            response = self.rekognition_client.start_face_detection(
                Video={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                },
                FaceAttributes='ALL'
            )
            
            return {'job_id': response['JobId'], 'type': 'face_detection'}
            
        except ClientError as e:
            logger.error(f"Failed to start face detection: {str(e)}")
            raise
    
    def detect_content_moderation(self, s3_key: str) -> Dict:
        """Start content moderation job"""
        try:
            response = self.rekognition_client.start_content_moderation(
                Video={
                    'S3Object': {
                        'Bucket': self.s3_bucket,
                        'Name': s3_key
                    }
                },
                MinConfidence=60
            )
            
            return {'job_id': response['JobId'], 'type': 'content_moderation'}
            
        except ClientError as e:
            logger.error(f"Failed to start content moderation: {str(e)}")
            raise
    
    # Transcribe Operations
    def start_transcription(self, s3_key: str, job_name: str) -> Dict:
        """
        Start transcription job for video audio
        
        Args:
            s3_key: S3 key of video file
            job_name: Unique name for transcription job
            
        Returns:
            Job information
        """
        try:
            media_uri = f"s3://{self.s3_bucket}/{s3_key}"
            
            response = self.transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': media_uri},
                MediaFormat='mp4',
                LanguageCode='en-US',
                Settings={
                    'ShowSpeakerLabels': True,
                    'MaxSpeakerLabels': 10
                }
            )
            
            logger.info(f"Started transcription job: {job_name}")
            return {
                'job_name': job_name,
                'status': response['TranscriptionJob']['TranscriptionJobStatus']
            }
            
        except ClientError as e:
            logger.error(f"Failed to start transcription: {str(e)}")
            raise
    
    def get_transcription_results(self, job_name: str) -> Dict:
        """Get transcription job results"""
        try:
            response = self.transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            job = response['TranscriptionJob']
            
            if job['TranscriptionJobStatus'] == 'COMPLETED':
                # Download and parse transcript
                transcript_uri = job['Transcript']['TranscriptFileUri']
                
                # Use boto3 to download the transcript JSON
                import requests
                transcript_response = requests.get(transcript_uri)
                transcript_data = transcript_response.json()
                
                return {
                    'status': 'completed',
                    'transcript': transcript_data['results']['transcripts'][0]['transcript'],
                    'items': transcript_data['results']['items'],
                    'language_code': job.get('LanguageCode', 'en-US')
                }
            
            return {'status': job['TranscriptionJobStatus']}
            
        except ClientError as e:
            logger.error(f"Failed to get transcription results: {str(e)}")
            raise
    
    # Comprehend Operations
    def analyze_text_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of transcribed text"""
        try:
            response = self.comprehend_client.detect_sentiment(
                Text=text[:5000],  # Comprehend has text limit
                LanguageCode='en'
            )
            
            return {
                'sentiment': response['Sentiment'],
                'scores': response['SentimentScore']
            }
            
        except ClientError as e:
            logger.error(f"Failed to analyze sentiment: {str(e)}")
            raise
    
    def extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text"""
        try:
            response = self.comprehend_client.detect_key_phrases(
                Text=text[:5000],
                LanguageCode='en'
            )
            
            return [phrase['Text'] for phrase in response['KeyPhrases']]
            
        except ClientError as e:
            logger.error(f"Failed to extract key phrases: {str(e)}")
            raise
    
    def detect_entities(self, text: str) -> List[Dict]:
        """Detect named entities in text"""
        try:
            response = self.comprehend_client.detect_entities(
                Text=text[:5000],
                LanguageCode='en'
            )
            
            return [{
                'text': entity['Text'],
                'type': entity['Type'],
                'score': entity['Score']
            } for entity in response['Entities']]
            
        except ClientError as e:
            logger.error(f"Failed to detect entities: {str(e)}")
            raise

# Singleton instance
aws_service = AWSService()