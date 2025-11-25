# Error Handling Architecture

## Overview
ClinXML implements a comprehensive error handling and resilience system to ensure reliable XML parsing, structured error reporting, and graceful degradation in healthcare environments. The system prioritises clinical data integrity whilst providing transparent error information for troubleshooting and audit purposes.

## Core Components

### Error Context Objects
**Location**: `utils/common/error_handling.py`

The error handling system uses structured context objects to capture comprehensive diagnostic information about parsing failures.

#### XMLParsingContext
Specialised context for XML parsing operations:
```python
@dataclass
class XMLParsingContext:
    element_name: Optional[str] = None           # Element being parsed
    element_path: Optional[str] = None           # XPath location
    parent_element: Optional[str] = None         # Parent element context
    attribute_name: Optional[str] = None         # Attribute being extracted
    expected_format: Optional[str] = None        # Expected data format
    actual_value: Optional[str] = None           # Actual value found
    parsing_stage: Optional[str] = None          # Stage of parsing
    validation_rules: Optional[list] = None      # Validation rules applied
    namespace_info: Optional[Dict[str, str]] = None  # Namespace context
    recovery_attempted: bool = False             # Recovery strategy tried
    recovery_strategies: Optional[list] = None   # Available recovery options
```

#### ParseResult
Structured result object for all parsing operations:
```python
@dataclass
class ParseResult:
    success: bool                                # Operation success status
    data: Optional[Any] = None                   # Parsed data (if successful)
    errors: Optional[list] = None                # Error messages
    warnings: Optional[list] = None              # Warning messages
    context: Optional[XMLParsingContext] = None  # Parsing context
```

### Enhanced Error Classes

#### XMLParsingError
Enhanced XML parsing error with comprehensive context:
```python
class XMLParsingError(EMISConverterError):
    def __init__(self, message: str, element_name: str = None, 
                 xml_context: Optional[XMLParsingContext] = None):
        self.element_name = element_name
        self.xml_context = xml_context
        # Provides get_technical_details() with XML-specific context
```

### Safe Parsing Methods
**Location**: `utils/xml_parsers/base_parser.py`

The base parser provides comprehensive safe parsing methods that return `ParseResult` objects instead of raising exceptions.

#### Core Safe Methods
```python
# Safe element finding
safe_find_element(parent, xpath, element_name) -> ParseResult

# Safe text extraction with validation
safe_get_text(element, element_name, expected_format) -> ParseResult

# Safe attribute extraction with validation
safe_get_attribute(element, attr, expected_format, required) -> ParseResult

# Safe multiple element finding
safe_find_elements(parent, xpath, element_name) -> ParseResult
```

#### Validation and Error Collection
```python
# Built-in format validation
_validate_format(value, expected_format) -> bool
# Supports: "numeric", "boolean", "date" validation

# Error and warning collection
add_parsing_error(error, context)
add_parsing_warning(warning, context)
clear_errors()
get_parsing_summary() -> Dict[str, Any]
```

## Structured Error Reporting System

### Diagnostic Logging
**Location**: `utils/common/error_handling.py`

Enhanced error handler with diagnostic capabilities:

#### Diagnostic Methods
```python
# XML-specific diagnostic logging
log_parsing_diagnostic(operation, element_name, context, message, level)

# Progress logging for large documents
log_parsing_progress(operation, total_elements, processed_elements, errors, warnings)

# Session summary for audit purposes
get_session_summary() -> Dict[str, Any]
```

#### Example Diagnostic Output
```
XML Parsing Diagnostic - criterion_parsing: Range boundary validation failed
Details: {
  'operation': 'range_boundary_parsing',
  'element_name': 'rangeFrom', 
  'element_path': '//restriction/rangeFrom',
  'parent_element': 'restriction',
  'expected_format': 'numeric',
  'actual_value': 'invalid_text',
  'parsing_stage': 'boundary_validation',
  'recovery_attempted': true,
  'recovery_strategies': ['default_value', 'skip_boundary']
}
```

### Batch Processing Reports
**Location**: `utils/common/error_handling.py`

Comprehensive batch processing error aggregation for enterprise environments.

#### BatchParsingReport
```python
@dataclass
class BatchParsingReport:
    operation_name: str                  # Operation identifier
    total_items: int = 0                # Total items to process
    successful_items: int = 0           # Successfully processed
    failed_items: int = 0               # Failed items
    warnings_count: int = 0             # Warning count
    errors: list = None                 # Detailed error list
    warnings: list = None               # Detailed warning list
    processing_time: Optional[float] = None  # Execution time
    
    @property
    def success_rate(self) -> float:
        # Calculate percentage success rate
```

#### BatchErrorAggregator
Manages multiple batch operations with pattern analysis:
```python
# Start batch processing tracking
aggregator.start_batch("criterion_parsing", total_items=50)

# Track individual item results
for item in items:
    result = safe_parse_item(item)
    aggregator.add_item_result(result)

# Complete batch with summary
report = aggregator.finish_batch()

# Analyse error patterns across batches
error_patterns = aggregator.get_error_patterns()
combined_report = aggregator.get_aggregated_report()
```

## Defensive Programming Enhancements

### Null Checking and Validation
**Location**: `utils/xml_parsers/criterion_parser.py`

Enhanced criterion parser with comprehensive null checking:

#### Safe Criterion Parsing
```python
def safe_parse_criterion(self, criterion_elem) -> ParseResult:
    # Comprehensive null checking and error collection
    errors = []
    warnings = []
    
    # Safe extraction with fallbacks
    criterion_id_result = self.safe_get_text(
        self.find_element_both(criterion_elem, 'id'),
        element_name="id",
        expected_format="string"
    )
    
    if not criterion_id_result.success:
        criterion_id = "Unknown"
        warnings.extend(criterion_id_result.warnings or [])
    
    # Continue with comprehensive error collection...
```

#### Component-Specific Safe Parsing
```python
# Safe value set parsing with error collection
_safe_parse_value_sets(criterion_elem, errors, warnings) -> List[Dict]

# Safe column filter parsing with validation
_safe_parse_column_filters(criterion_elem, errors, warnings) -> List[Dict]

# Safe restriction parsing with error handling
_safe_parse_restrictions(criterion_elem, errors, warnings) -> List[Any]

# Safe linked criteria parsing with hierarchy validation
_safe_parse_linked_criteria(criterion_elem, errors, warnings) -> List['SearchCriterion']
```

### Robust Range Boundary Parsing
**Location**: `utils/xml_parsers/criterion_parser.py`

Enhanced range parsing with comprehensive validation:

#### Safe Range Parsing
```python
def safe_parse_range_value(self, range_elem) -> ParseResult:
    # Comprehensive range validation
    xml_context = create_xml_parsing_context(
        element_name="rangeValue",
        parsing_stage="range_parsing"
    )
    
    # Validate relative_to attribute
    valid_relative_values = ['baseline', 'encounter', 'current', 'previous']
    
    # Parse boundaries with validation
    boundary_result = self.safe_parse_range_boundary(range_from_result.data)
    
    # Validate range logic consistency
    validation_warnings = self._validate_range_boundaries(from_boundary, to_boundary)
```

#### Boundary Validation
```python
def _validate_range_boundaries(self, from_boundary, to_boundary) -> List[str]:
    # Logical consistency checking
    # Numeric value validation
    # Unit consistency validation
    # Operator compatibility validation
```

### Defensive Demographic Detection
**Location**: `utils/xml_parsers/criterion_parser.py`

Multi-level demographic detection with confidence scoring:

#### Enhanced Detection
```python
@staticmethod
def safe_detect_demographics_column(column_name, context="") -> Dict[str, Any]:
    result = {
        'is_demographics': False,
        'demographics_type': None,
        'confidence': 'none',          # none, very_low, low, medium, high
        'matched_patterns': [],
        'warnings': [],
        'context': context
    }
    
    # Primary LSOA patterns (high confidence)
    lsoa_patterns = [
        r'.*LOWER_AREA.*20\d{2}.*',     # Year pattern 2000-2099
        r'.*LONDON_LOWER_AREA.*',       # London specific
        r'.*LSOA.*20\d{2}.*',          # Direct LSOA
        r'.*LOWER_SUPER_OUTPUT_AREA.*'  # Full form
    ]
    
    # Secondary geographical patterns (medium confidence)
    geo_patterns = [
        r'.*MSOA.*',           # Middle Layer Super Output Area
        r'.*WARD.*',           # Electoral wards
        r'.*POSTCODE.*AREA.*', # Postcode areas
        r'.*CCG.*',            # Clinical Commissioning Group
    ]
    
    # Tertiary patient patterns (low confidence)
    patient_patterns = [
        r'.*PATIENT.*AGE.*',
        r'.*PATIENT.*GENDER.*',
        r'.*ETHNICITY.*',
        r'.*DEMOGRAPHIC.*'
    ]
    
    # Fallback keyword detection (very low confidence)
    demographic_keywords = [
        'DEPRIVATION', 'INCOME', 'RURAL', 'URBAN', 'POPULATION'
    ]
```

#### Bulk Analysis
```python
@staticmethod
def get_demographics_classification_summary(columns) -> Dict[str, Any]:
    # Bulk column analysis with pattern statistics
    # Confidence distribution analysis
    # Error and warning aggregation
    # Performance metrics
```

## XML Structure Validation

### Comprehensive Structure Validation
**Location**: `utils/xml_parsers/base_parser.py`

Schema-based XML structure validation:

#### Structure Validation
```python
def validate_xml_structure(self, root_element, expected_schema) -> ParseResult:
    expected_schema = {
        'required_elements': ['element1', 'element2'],
        'optional_elements': ['element3'],
        'required_attributes': {'element1': ['attr1', 'attr2']},
        'namespaces': ['emis'],
        'max_depth': 10
    }
    
    # Multi-level validation
    validation_results = {
        'required_elements': self._validate_required_elements(...),
        'depth_check': self._validate_element_depth(...),
        'namespace_check': self._validate_namespace_usage(...),
        'attribute_check': self._validate_required_attributes(...),
        'malformed_check': self._check_malformed_patterns(...)
    }
```

#### Validation Components
```python
# Required element validation with duplicate detection
_validate_required_elements(root, required, errors, warnings) -> Dict[str, bool]

# Depth validation to prevent performance issues
_validate_element_depth(root, max_depth, warnings) -> Dict[str, Any]

# Namespace consistency validation
_validate_namespace_usage(root, expected_namespaces, warnings) -> Dict[str, Any]

# Required attribute validation
_validate_required_attributes(root, required_attrs, errors, warnings) -> Dict[str, Dict[str, bool]]

# Malformed pattern detection
_check_malformed_patterns(root, warnings) -> Dict[str, Any]
```

#### Malformed Pattern Detection
```python
def _check_malformed_patterns(self, root, warnings) -> Dict[str, Any]:
    issues = {
        'empty_elements': 0,           # Elements without content
        'very_long_text': 0,          # Suspiciously long text
        'suspicious_characters': 0,    # Potential encoding issues
        'unusual_tag_names': []       # Non-standard tag names
    }
    
    # Comprehensive pattern detection with thresholds
```

## Enhanced Parsing Logic

### Semantic Value Set Deduplication
**Location**: `utils/xml_parsers/value_set_parser.py`

Content-based deduplication beyond simple ID matching:

#### Semantic Deduplication
```python
def semantic_deduplicate_value_sets(self, value_sets) -> ParseResult:
    # Multi-strategy deduplication:
    # 1. Exact code match - merge identical code sets
    # 2. Hierarchical relationship - keep parents, remove children  
    # 3. Quality-based selection - keep highest quality set
    
    # Group by semantic similarity
    semantic_groups = self._group_by_semantic_similarity(value_sets)
    
    for group_sets in semantic_groups.values():
        dedup_result = self._deduplicate_semantic_group(group_sets)
        # Apply appropriate strategy based on relationships
```

#### Deduplication Strategies
```python
# Strategy 1: Exact code matching
_group_by_exact_codes(value_sets) -> Dict[str, List[Dict]]
_merge_identical_code_sets(code_sets) -> Dict

# Strategy 2: Hierarchical relationships  
_resolve_hierarchical_duplicates(group_sets) -> Dict[str, Any]

# Strategy 3: Quality-based selection
_select_best_quality_set(group_sets) -> Dict[str, Any]
_calculate_quality_score(value_set) -> int
```

#### Quality Scoring
```python
def _calculate_quality_score(self, value_set) -> int:
    score = 0
    
    # Points for completeness
    if value_set.get('description'): score += 10
    score += len(value_set.get('values', []))
    if value_set.get('code_system'): score += 5
    
    # Bonus for standard code systems
    code_system = value_set.get('code_system', '').lower()
    if 'snomed' in code_system: score += 20
    elif 'icd' in code_system: score += 15
    
    # Bonus for refsets
    if any(val.get('is_refset', False) for val in value_set.get('values', [])):
        score += 15
    
    return score
```

## Integration and Usage Patterns

### Safe XML Parsing Workflow
```python
from utils.common.error_handling import (
    ParseResult, create_xml_parsing_context, 
    get_batch_aggregator, safe_xml_parse
)

# Start batch processing
batch_aggregator = get_batch_aggregator()
batch_report = batch_aggregator.start_batch("xml_processing", total_items=len(criteria))

# Process each criterion with error collection
for criterion_elem in criteria:
    xml_context = create_xml_parsing_context(
        element_name="criterion",
        parsing_stage="criterion_parsing"
    )
    
    # Safe parsing with structured results
    result = parser.safe_parse_criterion(criterion_elem)
    
    # Add to batch tracking
    batch_aggregator.add_item_result(result, xml_context)
    
    if result.success:
        processed_criteria.append(result.data)
    else:
        # Handle errors without breaking processing
        for error in result.errors:
            logger.error(f"Criterion parsing failed: {error}")

# Complete batch with comprehensive reporting
final_report = batch_aggregator.finish_batch()
```

### Error Handler Integration
```python
from utils.common.error_handling import get_error_handler

# Get global error handler
error_handler = get_error_handler()

# Diagnostic logging
error_handler.log_parsing_diagnostic(
    operation="range_parsing",
    element_name="rangeFrom",
    context=xml_context,
    message="Boundary validation failed",
    level="warning"
)

# Progress tracking for large documents
error_handler.log_parsing_progress(
    operation="criterion_parsing",
    total_elements=100,
    processed_elements=75,
    errors=2,
    warnings=5
)

# Session summary for audit
session_summary = error_handler.get_session_summary()
```

### Value Set Deduplication Integration
```python
from utils.xml_parsers.value_set_parser import ValueSetParser

parser = ValueSetParser()

# Parse all value sets with error collection
value_sets = []
for vs_elem in value_set_elements:
    vs_result = parser.parse_value_set(vs_elem)
    if vs_result:
        value_sets.append(vs_result)

# Semantic deduplication with detailed reporting
dedup_result = parser.semantic_deduplicate_value_sets(value_sets)

if dedup_result.success:
    deduplicated_sets = dedup_result.data['deduplicated']
    removed_count = dedup_result.data['removed_duplicates']
    summary = dedup_result.data['deduplication_summary']
    
    logger.info(f"Deduplicated {removed_count} value sets")
    logger.info(f"Final count: {len(deduplicated_sets)}")
    
    if dedup_result.warnings:
        for warning in dedup_result.warnings:
            logger.warning(f"Deduplication warning: {warning}")
```

## Error Recovery and Resilience

### Recovery Strategies
The error handling system implements multiple recovery strategies:

#### Graceful Degradation
1. **Partial Success**: Continue processing when non-critical elements fail
2. **Default Values**: Use sensible defaults for missing optional data
3. **Fallback Patterns**: Multiple detection strategies for demographic data
4. **Skip and Continue**: Log errors but continue processing remaining items

#### Error Context Preservation
1. **Comprehensive Context**: Capture all relevant parsing context
2. **Recovery Documentation**: Track attempted recovery strategies
3. **Audit Trail**: Maintain complete error history for review
4. **Diagnostic Information**: Detailed technical context for debugging

### Clinical Data Integrity
The system prioritises clinical data integrity through:

#### Validation at Multiple Levels
1. **Format Validation**: Data type and format checking
2. **Logical Validation**: Range boundary consistency
3. **Semantic Validation**: Clinical code system validation
4. **Structural Validation**: XML schema compliance

#### Transparency for Clinical Review
1. **Warning Classification**: Distinguish warnings from errors
2. **Confidence Scoring**: Demographic detection confidence levels
3. **Pattern Analysis**: Error pattern recognition across batches
4. **Audit Reporting**: Comprehensive processing reports

## Performance Optimisation

### Error Handling Performance
The error handling system is designed for minimal performance impact:

#### Efficient Error Collection
- **Structured Objects**: Avoid expensive string formatting until needed
- **Lazy Evaluation**: Only generate detailed context when errors occur
- **Batch Processing**: Collect errors efficiently across large documents
- **Memory Management**: Clear error collections appropriately

#### Caching Strategy
- **Error Pattern Caching**: Cache validation results for repeated patterns
- **Context Reuse**: Reuse parsing context objects where possible
- **Selective Logging**: Only log when debug mode is enabled

### Memory Management
```python
# Efficient error collection
class XMLParserBase:
    def __init__(self):
        self._parsing_errors = []      # Collect errors during parsing
        self._parsing_warnings = []    # Collect warnings during parsing
    
    def clear_errors(self):
        """Clear accumulated errors to free memory"""
        self._parsing_errors.clear()
        self._parsing_warnings.clear()
    
    def get_parsing_summary(self) -> Dict[str, Any]:
        """Get summary without copying large error collections"""
        return {
            "error_count": len(self._parsing_errors),
            "warning_count": len(self._parsing_warnings)
        }
```

## Testing and Validation

### Unit Test Coverage
**Location**: `tests/test_error_handling.py`

Comprehensive test coverage includes:

#### Error Context Testing
- XMLParsingContext creation and serialisation
- ParseResult success/failure scenarios
- Error message formatting and clarity
- Context preservation across parsing operations

#### Safe Parsing Testing
- Null element handling
- Invalid XML structure handling
- Format validation accuracy
- Recovery strategy effectiveness

#### Batch Processing Testing
- Batch report generation accuracy
- Error pattern analysis validation
- Performance under load
- Memory usage monitoring

### Integration Testing
- End-to-end XML parsing with error injection
- Error reporting in UI components
- Audit trail completeness
- Clinical workflow error handling

### Performance Testing
- Large XML document parsing with errors
- Memory usage under error conditions
- Error logging performance impact
- Batch processing scalability

## Configuration and Monitoring

### Error Handler Configuration
The error handling system supports configuration for different deployment environments:

#### Production Configuration
```python
# Reduced verbosity for production
ERROR_LOGGING_LEVEL = "WARNING"
DETAILED_CONTEXT_ENABLED = False
PERFORMANCE_MONITORING = True

# Audit-focused configuration
AUDIT_TRAIL_ENABLED = True
ERROR_PATTERN_ANALYSIS = True
BATCH_REPORTING_ENABLED = True
```

#### Development Configuration
```python
# Full diagnostics for development
ERROR_LOGGING_LEVEL = "DEBUG"
DETAILED_CONTEXT_ENABLED = True
VALIDATION_STRICT_MODE = True

# Debug features
XML_STRUCTURE_VALIDATION = True
MALFORMED_PATTERN_DETECTION = True
COMPREHENSIVE_LOGGING = True
```

### Monitoring and Alerting
The system provides monitoring capabilities for enterprise deployment:

#### Error Metrics
- Error rate by parsing operation
- Most common error patterns
- Performance impact of error handling
- Memory usage during error conditions

#### Audit Capabilities  
- Complete parsing audit trails
- Error context preservation
- Clinical data integrity reports
- Compliance documentation generation

## Benefits

### Clinical Benefits
- **Data Integrity**: Comprehensive validation ensures clinical data quality
- **Transparency**: Clear error reporting for clinical review and audit
- **Reliability**: Graceful degradation maintains workflow continuity
- **Compliance**: Audit trails support regulatory requirements

### Development Benefits
- **Maintainability**: Structured error handling reduces debugging time
- **Reliability**: Comprehensive error coverage prevents silent failures
- **Debugging**: Rich context information accelerates issue resolution
- **Testing**: Structured error objects enable thorough testing

### Operational Benefits
- **Monitoring**: Comprehensive error metrics for system health
- **Performance**: Efficient error handling with minimal overhead
- **Scalability**: Batch processing supports large-scale operations
- **Recovery**: Multiple recovery strategies ensure system resilience

### User Benefits
- **Reliability**: Fewer crashes and unexpected failures
- **Transparency**: Clear understanding of processing issues
- **Performance**: Continued operation despite minor parsing issues
- **Trust**: Confidence in clinical data processing accuracy

## Best Practices

### Error Handling Implementation
1. **Use Structured Results**: Always return `ParseResult` objects from parsing operations
2. **Provide Rich Context**: Include comprehensive `XMLParsingContext` for failures
3. **Collect, Don't Crash**: Collect errors and warnings rather than throwing exceptions
4. **Validate Early**: Perform validation at the earliest possible stage

### Error Recovery
1. **Multiple Strategies**: Implement multiple recovery strategies for different error types
2. **Graceful Degradation**: Continue processing when possible with appropriate warnings
3. **Document Recovery**: Track attempted recovery strategies in error context
4. **User Communication**: Provide clear, actionable error messages to users

### Performance Considerations
1. **Lazy Context Generation**: Only generate expensive context when errors occur
2. **Batch Error Collection**: Collect errors efficiently for large document processing
3. **Memory Management**: Clear error collections appropriately to prevent memory leaks
4. **Selective Logging**: Use debug mode flags to control logging overhead

### Clinical Data Integrity
1. **Comprehensive Validation**: Validate at multiple levels (format, logic, semantic)
2. **Confidence Scoring**: Provide confidence levels for uncertain classifications
3. **Audit Trails**: Maintain complete processing history for compliance
4. **Transparency**: Surface warnings and errors appropriately for clinical review

This comprehensive error handling architecture ensures that ClinXML can reliably process clinical XML data whilst providing the transparency, audit capabilities, and data integrity required for healthcare environments.