# EMIS XML Search Patterns Reference

Technical reference for all currently encountered EMIS XML search patterns, structures, and implementation details.

## Table Types

### Core Tables
- **EVENTS**: Clinical codes, dates, and diagnostic information
- **MEDICATION_ISSUES**: Drug prescriptions, issue dates, drug codes
- **MEDICATION_COURSES**: Medication courses (distinct from individual issues) - course-level tracking
- **PATIENTS**: Demographics, registration dates, age, DOB
- **GPES_JOURNALS**: GP clinical system journals and registration tracking

## Column Types and Usage

### Clinical Data
- **READCODE**: Legacy Read codes for clinical conditions
- **SNOMEDCODE**: SNOMED CT concept codes
- **CONCEPT_ID**: SNOMED CT concept identifiers
- **CODE_DESCRIPTION**: Human-readable code descriptions

### Medication Data
- **DRUGCODE**: Drug product codes
- **DISPLAYTERM**: Drug display names and descriptions (formatted medication descriptions)
- **ISSUE_DATE**: Date medication was issued/prescribed
- **COMMENCE_DATE**: Course-level medication start date
- **LASTISSUE_DATE**: Course-level last issue date
- **QUANTITY_UNIT**: Standardized quantity measurements

### Date/Time Columns
- **DATE**: Generic date field (clinical events)
- **DOB**: Date of birth (patient demographics)
- **GMS_DATE_OF_REGISTRATION**: GP practice registration date
- **ISSUE_DATE**: Medication issue dates

### Demographics
- **AGE**: Current patient age
- **AGE_AT_EVENT**: Age at time of specific clinical event
- **SEX**: Patient gender
- **PATIENT**: EMIS patient identifier

### Patient Demographics Data
- **LONDON_LOWER_AREA_2011**: Lower Layer Super Output Area codes for all of England and Wales (2011 Census)
- **Note**: Despite "LONDON" in the column name, this covers all LSOA areas nationwide (naming quirk in EMIS)
- **Purpose**: Index of Multiple Deprivation (IMD) analysis and patient demographics filtering

### Organization and Practice Data
- **ORGANISATION_TERM**: Practice/organization names
- **USUAL_GP.USER_NAME**: Assigned clinician details

### Enhanced Clinical Data
- **ASSOCIATEDTEXT**: Free-text clinical notes
- **NUMERIC_VALUE**: Clinical measurement values (test results, measurements)

### Clinical Workflow
- **EPISODE**: Clinical episode states (FIRST, NEW, REVIEW, ENDED, NONE)

## Date and Time Filtering Patterns

### Relative Dates
- **Format**: `<value>-6</value><unit>MONTH</unit><relation>RELATIVE</relation>`
- **Examples**: -6 MONTH, +186 DAY, -1 YEAR
- **Usage**: Rolling time windows from current date or baseline

### Variable-Based Temporal Patterns
Modern EMIS versions support named temporal variables within `<singleValue><variable>` structures for intuitive date filtering.

#### Named Temporal Variables
All time units support Last/This/Next patterns:

##### Daily Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>DAY</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Daily tracking and immediate reporting

##### Weekly Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>WEEK</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Weekly reporting cycles

##### Monthly Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>MONTH</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Monthly reporting cycles

#### Quarterly Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>QUARTER</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Quarter-based reporting and claims tracking

#### Weekly Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>WEEK</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Recent activity tracking

#### Monthly Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>MONTH</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Monthly reporting cycles

#### Annual Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>YEAR</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Annual reporting and review cycles

#### Fiscal Year Variables
```xml
<singleValue>
    <variable>
        <value>Last</value>
        <unit>FISCALYEAR</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Values**: Last, This, Next
- **Usage**: Financial year reporting (April-March cycles)

#### Numeric Offset Variables
All time units support positive and negative numeric offsets:

```xml
<singleValue>
    <variable>
        <value>-1</value>
        <unit>MONTH</unit>
        <relation>RELATIVE</relation>
    </variable>
</singleValue>
```
- **Pattern**: Any integer (positive/negative) + any time unit
- **Examples**: -12 MONTH, 3 WEEK, -5 DAY, 2 QUARTER, -1 YEAR, 6 FISCALYEAR
- **Usage**: Precise offset calculations from search date
- **Units Supported**: DAY, WEEK, MONTH, QUARTER, YEAR, FISCALYEAR

### Range-Based Temporal Patterns

All temporal variable patterns can also be used in date ranges with `rangeFrom` and `rangeTo` boundaries:

#### Temporal Variable Ranges
```xml
<rangeValue>
    <rangeFrom>
        <value>
            <value>Last</value>
            <unit>QUARTER</unit>
            <relation>RELATIVE</relation>
        </value>
        <operator>GTEQ</operator>
    </rangeFrom>
    <rangeTo>
        <value>
            <value>-1</value>
            <unit>YEAR</unit>
            <relation>RELATIVE</relation>
        </value>
        <operator>LTEQ</operator>
    </rangeTo>
</rangeValue>
```
- **Pattern**: Any temporal variable can be used as range boundary
- **Operators**: GTEQ (>=), LTEQ (<=), GT (>), LT (<), EQ (=)
- **Usage**: Complex date filtering with "between" logic

#### Range Examples

**Quarterly Range:**
```xml
<rangeFrom>
    <value>
        <value>This</value>
        <unit>QUARTER</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>GTEQ</operator>
</rangeFrom>
<rangeTo>
    <value>
        <value>Next</value>
        <unit>QUARTER</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>LTEQ</operator>
</rangeTo>
```

**Numeric Offset Range:**
```xml
<rangeFrom>
    <value>
        <value>-6</value>
        <unit>MONTH</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>GTEQ</operator>
</rangeFrom>
<rangeTo>
    <value>
        <value>3</value>
        <unit>MONTH</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>LTEQ</operator>
</rangeTo>
```

**Mixed Unit Range:**
```xml
<rangeFrom>
    <value>
        <value>Last</value>
        <unit>FISCALYEAR</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>GTEQ</operator>
</rangeFrom>
<rangeTo>
    <value>
        <value>30</value>
        <unit>DAY</unit>
        <relation>RELATIVE</relation>
    </value>
    <operator>LTEQ</operator>
</rangeTo>
```

## Report Context Temporal Patterns

The same temporal variable patterns appear in all EMIS report types but with different nesting structures:

### List Report Date Patterns
```xml
<listReport>
    <columnGroups>
        <columnGroup>
            <criteria>
                <criterion>
                    <filterAttribute>
                        <columnValue>
                            <column>ISSUE_DATE</column>
                            <rangeValue>
                                <rangeFrom>
                                    <value>
                                        <value>Last</value>
                                        <unit>QUARTER</unit>
                                        <relation>RELATIVE</relation>
                                    </value>
                                    <operator>GTEQ</operator>
                                </rangeFrom>
                                <rangeTo>
                                    <value>
                                        <value>3</value>
                                        <unit>MONTH</unit>
                                        <relation>RELATIVE</relation>
                                    </value>
                                    <operator>LTEQ</operator>
                                </rangeTo>
                            </rangeValue>
                        </columnValue>
                    </filterAttribute>
                </criterion>
            </criteria>
        </columnGroup>
    </columnGroups>
</listReport>
```

### Audit Report Date Patterns
```xml
<auditReport>
    <columnGroups>
        <columnGroup>
            <criteria>
                <criterion>
                    <filterAttribute>
                        <columnValue>
                            <column>DATE</column>
                            <rangeValue>
                                <rangeFrom>
                                    <value>
                                        <value>This</value>
                                        <unit>FISCALYEAR</unit>
                                        <relation>RELATIVE</relation>
                                    </value>
                                    <operator>GTEQ</operator>
                                </rangeFrom>
                            </rangeValue>
                        </columnValue>
                    </filterAttribute>
                </criterion>
            </criteria>
        </columnGroup>
    </columnGroups>
</auditReport>
```

### Aggregate Report Date Patterns
```xml
<aggregateReport>
    <criteria>
        <criterion>
            <filterAttribute>
                <columnValue>
                    <column>DATE</column>
                    <rangeValue>
                        <rangeFrom>
                            <value>
                                <value>-6</value>
                                <unit>MONTH</unit>
                                <relation>RELATIVE</relation>
                            </value>
                            <operator>GTEQ</operator>
                        </rangeFrom>
                    </rangeValue>
                </columnValue>
            </filterAttribute>
        </criterion>
    </criteria>
</aggregateReport>
```

All temporal patterns work identically across search and report contexts. Only the XML nesting structure differs.

### Absolute Dates
- **Format**: `<value>01/04/2023</value><relation>ABSOLUTE</relation>`
- **Usage**: Fixed regulatory boundaries, QOF reporting periods
- **Common Dates**: 01/04/2003, 01/04/2012, 01/04/2023 (QOF year boundaries)

### Baseline References
- **Format**: `relativeTo="BASELINE"`
- **Usage**: Reference point for search execution

### Age-Based Filtering
- **Simple Age**: `AGE >= 17 YEAR`
- **Age Ranges**: `rangeFrom 50 YEAR` AND `rangeTo 74 YEAR`
- **Age at Event**: `AGE_AT_EVENT < 248 DAY` (pediatric calculations)

## Search Restriction Types

### Simple Restrictions
- **Latest Records**: "Latest 1", "Latest 3"
- **Earliest Records**: "Earliest 1"
- **Current Status**: "Is Current", "Is Active"

### Conditional Restrictions
- **Format**: "Latest 1 WHERE READCODE IN (value_set)"
- **Purpose**: Filter records before applying restriction
- **Examples**: Latest HbA1c WHERE test type matches criteria

### Test Attributes
- **Numeric Tests**: "WHERE NUMERIC_VALUE <= -2.5"
- **Code Tests**: "WHERE READCODE IN (specific_codes)"
- **Date Tests**: Complex date boundary conditions

## Value Set Patterns

### SNOMED Concept Sets
- **Format**: `<codeSystem>SNOMED_CONCEPT</codeSystem>`
- **Hierarchy**: `<includeChildren>true</includeChildren>` for concept descendants
- **Usage**: Clinical condition definitions, medication classes

### Library Items
- **Format**: `<libraryItem>GUID</libraryItem>`
- **Purpose**: EMIS internal code libraries and reference sets
- **Usage**: Standardized clinical code groupings

### Exception Codes
- **DIAG_DAT**: Diagnosis date exceptions (QOF reporting)
- **MDRV_DAT**: Medical review date exceptions
- **PAT_AGE**: Patient age exceptions
- **Purpose**: QOF quality indicator exclusions

## Logical Operators and Structure

### Criteria Group Logic
- **AND Logic**: `<memberOperator>AND</memberOperator>`
- **OR Logic**: `<memberOperator>OR</memberOperator>`
- **Negation**: `<negation>true</negation>` for exclusion logic

### Filter Operators
- **Inclusion**: `<inNotIn>IN</inNotIn>`
- **Exclusion**: `<inNotIn>NOT IN</inNotIn>`
- **Comparison**: GT, LT, GTEQ, LTEQ, EQ

### Base Criteria Group Structures (Nested Criterion Logic)

Complex criteria can contain nested `baseCriteriaGroup` elements that house the actual clinical logic within wrapper criteria. This pattern is used for multi-part clinical logic where the main criterion acts as a container.

#### Structure Pattern
```xml
<criterion>
  <id>main-criterion-id</id>
  <table>EVENTS</table>
  <displayName>Clinical Codes</displayName>
  
  <!-- Main criterion may have date filters only -->
  <filterAttribute>
    <columnValue>
      <column>DATE</column>
      <rangeValue>...</rangeValue>
    </columnValue>
    <restriction>...</restriction>
  </filterAttribute>
  
  <!-- Actual clinical logic nested in baseCriteriaGroup -->
  <baseCriteriaGroup>
    <definition>
      <memberOperator>AND</memberOperator>
      <criteria>
        <criterion>
          <id>nested-criterion-1</id>
          <filterAttribute>
            <columnValue>
              <column>READCODE</column>
              <valueSet>
                <description>COPD_COD</description>
                <values>...</values>
              </valueSet>
            </columnValue>
          </filterAttribute>
        </criterion>
        <criterion>
          <id>nested-criterion-2</id>
          <negation>true</negation>
          <filterAttribute>
            <columnValue>
              <column>READCODE</column>
              <valueSet>
                <description>COPDRES_COD</description>
                <values>...</values>
              </valueSet>
            </columnValue>
          </filterAttribute>
        </criterion>
      </criteria>
    </definition>
  </baseCriteriaGroup>
  
  <!-- Multiple baseCriteriaGroup elements possible -->
  <baseCriteriaGroup>
    <definition>
      <memberOperator>AND</memberOperator>
      <criteria>...</criteria>
    </definition>
  </baseCriteriaGroup>
</criterion>
```

#### Usage Patterns
- **Complex Clinical Logic**: Multi-part diagnosis criteria with resolution tracking
- **QOF Register Logic**: Diagnosis + resolution tracking with date boundaries
- **Nested Exclusions**: Include condition A AND exclude condition B with temporal constraints
- **Clinical Workflow**: Complex pathways requiring multiple related criteria

#### Implementation Requirements
- **Value Set Extraction**: Must parse value sets from nested criteria within baseCriteriaGroup
- **Restriction Merging**: Main criterion restrictions combined with nested criterion restrictions
- **Display Logic**: Present nested criteria as components of main criterion
- **Linked Criteria Support**: Nested criteria can contain their own linkedCriterion elements

## Cross-Table Relationships (Linked Criteria)

### Common Patterns
- **EVENTS → MEDICATION_ISSUES**: Clinical condition to treatment tracking
- **PATIENTS → EVENTS**: Demographics to clinical events
- **MEDICATION_ISSUES → PATIENTS**: Prescriptions to patient context

### Date Relationships
- **GMS Registration to Clinical Events**: Practice registration context
- **DOB to Event Dates**: Age calculations and pediatric workflows
- **Issue Date to Clinical Date**: Medication timing validation

### Relationship Operators
Date relationships in linked criteria specify temporal logic using operators:
- **GT**: Greater than (e.g., `<value>0</value><unit>DAY</unit><operator>GT</operator>` = "more than 0 days after")
- **GTE/GTEQ**: Greater than or equal to
- **LT**: Less than
- **LTE/LTEQ**: Less than or equal to
- **EQ**: Equal to (default behavior if no operator specified)

Example XML structure:
```xml
<linkedCriterion>
  <relationship>
    <parentColumn>DATE</parentColumn>
    <childColumn>DATE</childColumn>
    <rangeValue>
      <rangeFrom>
        <value><value>0</value><unit>DAY</unit></value>
        <operator>GT</operator>
      </rangeFrom>
    </rangeValue>
  </relationship>
  <criterion>...</criterion>
</linkedCriterion>
```

### Complex Calculations
- **Day Range Calculations**: -93 to +186 days between linked events
- **Age at Event**: Birth date to clinical event age calculations
- **Vaccine Timing**: Multi-dose scheduling with contraindication logic

## Report Type Classification

### Search Reports (Population-based)
- **Structure**: `<population><criteriaGroup>`
- **Parent Type**: `ACTIVE` (independent)
- **Purpose**: Define patient populations using search criteria

### List Reports
- **Structure**: `<listReport><columnGroups>`
- **Parent Type**: `POP` with `<SearchIdentifier>` reference
- **Parent Reference**: `<parent parentType="POP"><SearchIdentifier reportGuid="..." /></parent>`
- **Purpose**: Multi-column search engine displaying detailed patient data with per-column filtering
- **Architecture**: Takes base population from parent search, then runs independent search criteria per column

#### Column Group Structure
- **Column Groups**: Multiple `<columnGroups>` each representing a logical table with independent search logic
  - `logicalTableName`: Database table (PATIENTS, EVENTS, MEDICATION_ISSUES, GPES_JOURNALS)
  - `displayName`: UI presentation name for the column group
  - `<columnar>`: Output column definitions (what data to display)
  - `<criteria>`: Full search criteria - can be as complex as main searches

#### Column-Level Search Capabilities
Each column group can contain:
- **Independent Search Criteria**: Clinical codes, medications, appointments, demographics
- **Own Restrictions**: Latest N, Earliest N, date ranges, conditional logic
- **Own Linked Criteria**: Cross-table relationships with complex date calculations
- **Field Selection**: Choose specific output fields

#### List Column Output Options
- **Clinical Data**: CODE_DESCRIPTION, CONCEPT_ID, DATE, LEGACY_CODE
- **Medication Data**: MEDICATION_NAME, ISSUE_DATE, AUTHORIZING_USER, DRUG_CODE
- **Appointment Data**: APPOINTMENT_DATE, CLINICIAN, SLOT_STATUS, DNA_STATUS
- **Demographics**: PATIENT, PATIENT_NAME, AGE, SEX, DOB, REGISTRATION_DATE

#### Column-Specific Restrictions
- **`<restriction><columnOrder>`**: Sorting and record limiting within each column group
- **`recordCount`**: Limit results per patient (Latest 1, Latest 5, etc.)
- **`direction`**: Sort order (ASC/DESC for date-based ordering)

#### List Report Restriction Pattern
List Reports use a nested restriction structure within column group criteria. Two patterns exist:

**Pattern 1: Restriction as sibling to columnValue (most common)**
```xml
<criterion>
  <filterAttribute>
    <columnValue>
      <valueSet>...</valueSet>
    </columnValue>
    <restriction>
      <columnOrder>
        <recordCount>5</recordCount>
        <columns>
          <column>DATE</column>
          <direction>DESC</direction>
        </columns>
      </columnOrder>
    </restriction>
  </filterAttribute>
</criterion>
```

**Pattern 2: Restriction under columnValue (alternative structure)**
```xml
<criterion>
  <filterAttribute>
    <columnValue>
      <valueSet>...</valueSet>
      <restriction>...</restriction>
    </columnValue>
  </filterAttribute>
</criterion>
```
- **Paths**: `filterAttribute > restriction` (Pattern 1) or `filterAttribute > columnValue > restriction` (Pattern 2)
- **Purpose**: Record count limits with column sorting applied to filtered clinical codes
- **Example**: "Latest 5 BMI recordings" filters for BMI codes then applies Latest 5 with DATE DESC sorting
- **Implementation**: Parser must check both direct criterion restrictions AND nested columnValue restrictions

### Audit Reports
- **Structure**: `<auditReport><customAggregate>` with multiple `<population>` references
- **Parent Type**: `ALL` (organizational reporting across all patients including left and deceased)
- **Purpose**: Quality monitoring, compliance tracking, and organizational aggregation

#### Two Types of Audit Reports

**1. Simple Audit Reports (PATIENTS table)**
- **Logical Table**: `PATIENTS` 
- **Structure**: Pure organizational aggregation without additional clinical criteria
- **Example**: Basic practice population counts grouped by organization

**2. Complex Audit Reports (EVENTS/other tables)**
- **Logical Table**: `EVENTS`, `MEDICATION_ISSUES`, `Consultations`, etc.
- **Structure**: Multi-population aggregation WITH additional filtering criteria
- **Example**: MED3 certificates across disease groups with date/user filters

#### Multi-Population Architecture
- **Population References**: Multiple `<population>GUID</population>` elements reference base searches
- **Member Searches**: Each population GUID corresponds to a separate search defining a patient cohort
- **Cross-Population Analysis**: Results show counts per search cohort with shared additional criteria

#### Organizational Grouping
- **Purpose**: Break down results by organizational/workflow attributes
- **Common Columns**: 
  - `ORGANISATION_NPC` (practice codes)
  - `USER` (clinician identifiers)  
  - `CONSULTATION` (consultation identifiers)
  - `SURNAME` (user surnames for audit trails)

#### Additional Criteria Layer
When using non-PATIENTS tables, Audit Reports can apply additional filtering criteria:
- **Clinical Codes**: Specific codes applied across all member populations
- **Date Filters**: Temporal restrictions
- **User Authorization**: Active user filters, authorization status
- **Record Restrictions**: Ordering (latest N), record counts

### Aggregate Reports
- **Structure**: `<aggregateReport><group><result>`
- **Parent Type**: `ACTIVE` (independent criteria)
- **Purpose**: Statistical analysis and cross-tabulation

## Parameter and User Input Patterns

### Dynamic Parameters
- **Format**: `<parameter><name>dynamicdate</name><allowGlobal>true</allowGlobal></parameter>`
- **Purpose**: Runtime user input for flexible date ranges
- **Scope**: Global (system-wide) or Local (search-specific)

### Library References
- **Internal Libraries**: EMIS code libraries referenced by GUID
- **External References**: NHS code sets and national libraries
- **Format**: `<valueSet><codeSystem>LIBRARY_ITEM</codeSystem><values><value>43682b4c-0a47-4fe1-a45d-9c6082ff8614</value></values></valueSet>`

### Global Parameters
- **Structure**: `<parameter><name>dynamicdate</name><allowGlobal>true</allowGlobal></parameter>`
- **Purpose**: Runtime user input with system-wide scope
- **Usage**: Flexible date ranges that can be shared across multiple searches

## Advanced EMIS Internal Classifications (EMISINTERNAL)

EMISINTERNAL codes can appear in both main search criteria and linked criteria depending on the search logic requirements. They provide workflow-level filtering beyond clinical codes.

### Episode Types
- **Basic Episodes**: `<valueSet><codeSystem>EMISINTERNAL</codeSystem><values><value>FIRST</value><value>NEW</value><value>REVIEW</value><value>ENDED</value><value>NONE</value></values></valueSet>`
- **Inverted Logic**: `<allValues><codeSystem>EMISINTERNAL</codeSystem><values><value>REVIEW</value></values><values><value>ENDED</value></values></allValues>`
- **Purpose**: Include all episodes EXCEPT those specified (REVIEW, ENDED)

### Consultation Context Filtering

#### Main Criterion EMISINTERNAL (Value Set Level)
```xml
<criterion>
  <table>EVENTS</table>
  <filterAttribute>
    <columnValue>
      <column>READCODE</column>
      <valueSet><codeSystem>SNOMED_CONCEPT</codeSystem>...</valueSet>
    </columnValue>
    <!-- EMISINTERNAL in main criterion -->
    <valueSet>
      <codeSystem>EMISINTERNAL</codeSystem>
      <values>
        <value>PROBLEM</value>
        <displayName>Problem</displayName>
      </values>
    </valueSet>
  </filterAttribute>
</criterion>
```

#### Linked Criterion EMISINTERNAL (Column Filter Level)
```xml
<linkedCriterion>
  <criterion>
    <table>EVENTS</table>
    <filterAttribute>
      <columnValue>
        <column>READCODE</column>
        <valueSet><codeSystem>SNOMED_CONCEPT</codeSystem>...</valueSet>
      </columnValue>
      <!-- EMISINTERNAL as column filter in linked criterion -->
      <columnValue>
        <column>CONSULTATION_HEADING</column>
        <displayName>Consultation Heading</displayName>
        <inNotIn>IN</inNotIn>
        <valueSet>
          <codeSystem>EMISINTERNAL</codeSystem>
          <values>
            <value>PROBLEM</value>
            <displayName>Problem</displayName>
            <includeChildren>false</includeChildren>
          </values>
        </valueSet>
      </columnValue>
    </filterAttribute>
  </criterion>
</linkedCriterion>
```

### EMISINTERNAL Classification Types

#### Consultation Heading Classifications
- **PROBLEM**: Problem-focused consultations
- **REVIEW**: Follow-up/review consultations  
- **ISSUE**: Administrative issues

#### Clinical Status Classifications  
- **COMPLICATION**: Complication events only
- **ONGOING**: Active/ongoing conditions
- **RESOLVED**: Resolved conditions

### Multi-Column EMISINTERNAL Patterns

#### User Authorization (AUTHOR + CURRENTLY_CONTRACTED)
```xml
<columnValue>
  <column>AUTHOR</column>
  <column>CURRENTLY_CONTRACTED</column>
  <displayName>EMISINTERNAL Classification</displayName>
  <inNotIn>IN</inNotIn>
  <valueSet>
    <codeSystem>EMISINTERNAL</codeSystem>
    <values>
      <value>Current</value>
      <displayName>Active</displayName>
    </values>
  </valueSet>
</columnValue>
```

**Purpose**: Ensure only active, contracted users are included in audit reports
**Multi-Column Logic**: Combines user identification (AUTHOR) with contract status (CURRENTLY_CONTRACTED)

### EMISINTERNAL Usage Context
- **Main Criteria**: Filter initial patient/event selection based on workflow context
- **Linked Criteria**: Apply additional workflow filters to related events
- **Column Filters**: Granular filtering within specific data columns (most common for CONSULTATION_HEADING)
- **Multi-Column**: Complex authorization and workflow state combinations
- **Audit Reports**: User authorization filters at aggregate level, separate from individual search logic

## Advanced Code System Classifications

### Drug Brand Names (SCT_APPNAME)
- **Brand-Specific**: `<valueSet><codeSystem>SCT_APPNAME</codeSystem><values><value>2067031000033115</value><displayName>Emerade</displayName><includeChildren>true</includeChildren></values></valueSet>`
- **Purpose**: MHRA drug safety alerts and brand-specific monitoring

### Legacy Code Mapping
- **Legacy Bridge**: `<values><value>4557141000033111</value><legacyValue>M-IN30563NEMIS</legacyValue><clusterCode>FlattenedCodeList</clusterCode></values>`
- **Purpose**: Backward compatibility with legacy EMIS system codes

### SNOMED Refsets
- **Refset Flag**: `<isRefset>true</isRefset>` for SNOMED CT reference sets
- **Palliative Care**: PALCARE_COD for palliative care coding
- **Frailty Assessment**: MILDFRAIL_COD, MODFRAIL_COD, SEVFRAIL_COD (Rockwood Scale)

### Medication-Specific Code Systems
- **SCT_APPNAME**: Application-specific medication names (Emerade, EpiPen, Jext auto-injectors)
- **SCT_CONST**: Constituent/generic drug names (Rivaroxaban, Apixaban, Dabigatran)
- **SCT_DRGGRP**: Drug group classifications (Hyperlipidaemia drugs, anticoagulants)

## Exception Code Patterns

### QOF Exception Codes
- **Basic Diagnosis**: `<exceptionCode>DIAG_DAT</exceptionCode>`
- **Medical Review**: `<exceptionCode>MDRV_DAT</exceptionCode>`
- **Patient Age**: `<exceptionCode>PAT_AGE</exceptionCode>`
- **Disease-Specific**: `<exceptionCode>DEPR_DAT1</exceptionCode>`, `<exceptionCode>HYP_DAT</exceptionCode>`
- **Combined**: `<exceptionCode>SEVFRAIL_DAT/MODFRAIL_COD</exceptionCode>`

### Exception Code Extensions
- **Frailty Exclusions**: `SEVFRAIL_DAT`, `MODFRAIL_COD` for assessment-based exclusions
- **Care Planning**: Exception codes for advance care planning scenarios

## Healthcare Quality Integration

### QOF Contract Information
- **Structure**: `<contractInformation><scoreNeeded>true</scoreNeeded><target>3</target></contractInformation>`
- **Indicator**: `<qmasIndicator>PC</qmasIndicator>`
- **Purpose**: Automated QOF scoring and compliance tracking

### Rockwood Clinical Frailty Scale
- **Level 1**: `<value>12737921000006110</value><displayName>Rockwood Clinical Frailty Scale level 1 - very fit</displayName>`
- **Level 9**: `<value>12738081000006111</value><displayName>Rockwood Clinical Frailty Scale level 9 - terminally ill</displayName>`
- **Purpose**: Standardized frailty assessment for palliative care pathways

### ReSPECT Form Integration
- **Structure**: `<value>12622651000006118</value><displayName>Has ReSPECT (Recommended Summary Plan for Emergency Care and Treatment)</displayName>`
- **Purpose**: Advance care planning and emergency response guidance

## Complex Date Relationships

### Absolute Dates with Regulatory Requirements
- **Format**: `<rangeValue><rangeFrom><value><value>01/04/2003</value><unit>DATE</unit><relation>ABSOLUTE</relation></value><operator>GTEQ</operator></rangeFrom></rangeValue>`
- **Usage**: QOF register requirements (cancer register since April 2003)

### Age at Event Calculations
- **Structure**: `<column>AGE_AT_EVENT</column><rangeValue><rangeTo><value><value>248</value><unit>DAY</unit><relation>RELATIVE</relation></value><operator>LT</operator></rangeTo></rangeValue>`
- **Purpose**: Vaccine timing (DTaP before 8 months = 248 days)

### Advanced Time Range Logic
- **Multi-Period Lookback**: `-12 MONTH` to `0 DAY` for historical context requirements
- **Extended Lookback**: `-60 MONTH` for long-term medication/device tracking
- **Complex Duration Logic**: `0 DAY` to `6 MONTH` for specialist referral timing

## Advanced Linked Criteria Patterns

### Drug Safety Monitoring with Replacement Logic
```xml
<linkedCriterion>
  <relationship>
    <parentColumn>ISSUE_DATE</parentColumn>
    <childColumn>ISSUE_DATE</childColumn>
    <rangeValue><rangeFrom><value>0</value><unit>DAY</unit></rangeFrom></rangeValue>
  </relationship>
  <criterion>
    <negation>true</negation>
    <valueSet>
      <values><value>1323431000033114</value><displayName>Jext</displayName></values>
      <values><value>479731000033110</value><displayName>Epipen</displayName></values>
    </valueSet>
  </criterion>
</linkedCriterion>
```
**Purpose**: MHRA alerts - finds patients with recalled drugs who have NOT received replacement alternatives

### Cross-Table Registration Relationships
- **GPES Integration**: `<table>GPES_JOURNALS</table><column>CODE</column><column>AGE_AT_EVENT</column><column>DATE</column>`
- **Purpose**: Links clinical events to practice registration history for context

### Complex Linked Criterion Patterns
- **Same-Date Exclusions**: `<linkedCriterion>` with empty relationship for same-event exclusions
- **Multi-Level Nesting**: Linked criteria within linked criteria for complex temporal logic
- **Negative Linked Logic**: NOTIN logic within linked criteria for exclusion patterns

## Multi-Column Combined Filtering

### Author and Organization Combined
- **Structure**: `<columnValue><column>AUTHOR</column><column>CURRENTLY_CONTRACTED</column><displayName>User Details' Currently Contracted</displayName></columnValue>`
- **Purpose**: Audit reports requiring active user validation across organizational boundaries

### Enhanced Column Output Types
- **Author + Organization**: `<column>AUTHOR</column><column>NATIONAL_PRACTICE_CODE</column>` combined
- **User Category**: `<column>USERCATEGORY_TERM</column>` for clinician type identification
- **Associated Text**: `<column>ASSOCIATEDTEXT</column>` for free-text clinical notes
- **Concept ID**: `<column>CONCEPT_ID</column>` for SNOMED CT concept identification

## Numeric Value Handling

### Positive Values
- **Spirometry**: FEV1/FVC ratios (< 0.7 for COPD diagnosis)
- **BMI Calculations**: Weight/height derived measurements

### Negative Values
- **DEXA Scores**: Bone density measurements (<= -2.5 for osteoporosis)
- **Z-Scores**: Standardized test results with negative thresholds

## Enterprise and Organizational Features

### Folder Structures
- **Hierarchical Organization**: Parent-child folder relationships
- **Report Grouping**: Multiple reports within folder containers
- **Enterprise Reporting**: `enterpriseReportingLevel="PATIENT_LEVEL"`

### Enterprise Reporting Structures
- **Nested Folders**: `<parentFolder>` with `<sequence>` ordering
- **Enterprise Levels**: `<enterpriseReportingLevel>PSEUDO_IDENTIFYING</enterpriseReportingLevel>`
- **Multi-Organization**: `<association><organisation>guid</organisation></association>` (multiple associations)
- **Version Independence**: `<VersionIndependentGUID>` for cross-version compatibility

### Organizational Association
- **Practice Codes**: Organization GUID associations
- **User Context**: Author tracking with `userInRole` references
- **Audit Trails**: Creation time and modification tracking

## Quality and Exception Handling

### QOF Exception Patterns
- **Diagnosis Date Exceptions**: DIAG_DAT for delayed diagnosis
- **Medical Review Exceptions**: MDRV_DAT for review date variations
- **Patient Age Exceptions**: PAT_AGE for age-based exclusions

### Data Quality Checks
- **Ethnicity Validation**: Code completeness checking
- **BMI Range Validation**: Physiological boundary checking
- **Date Boundary Validation**: Recent absolute dates for data currency

## Advanced Patterns

### Multi-Dose Tracking
- **Vaccine Sequences**: 3+ doses with age and timing constraints
- **Contraindication Logic**: Medical exclusions with date-based rules
- **Schedule Compliance**: Complex multi-visit tracking

### Polypharmacy Analysis
- **Drug Interaction Checking**: Multiple medication analysis
- **Pathway Compliance**: Treatment protocol adherence
- **Tirzepatide Pathways**: Specific medication pathway tracking

### Risk Stratification
- **QOF Register Collections**: Multiple condition risk assessment
- **Large-Scale Analysis**: Enterprise-wide data stratification
- **Population Health**: Demographic and clinical risk scoring

### Population References
- **Cross-Search Logic**: `<populationCriterion reportGuid="..." />` for complex inclusion/exclusion
- **Search Chaining**: Multi-level search dependencies

### Advanced Episode Filtering
- **NOTIN Logic**: `<column>EPISODE</column>` with exclusions (REVIEW, FLARE, ENDED)
- **Dynamic Status**: Episode state changes over time

## Advanced Temporal Logic

### Quarterly Reporting
- **Quarter-Based Variables**: `<variable><value>Last</value><unit>QUARTER</unit>`
- **This vs Last Quarter**: `<value>This</value><unit>QUARTER</unit>` vs `<value>Last</value><unit>QUARTER</unit>`
- **Multi-Period Exclusions**: Exclude previous quarter claims while including current quarter
- **Complex Date Ranges**: Multiple date column filters within single criterion

### Test Attributes in Restrictions
- **Pattern**: `<restriction><testAttribute><columnValue>` for conditional filtering
- **Purpose**: Additional criteria that must be met within the restriction
- **Example**: Latest 1 record WHERE date is in specific quarter AND meets test criteria
- **Logic**: Multi-layered filtering beyond basic record counting

### Test Attributes with Value Sets
- **Pattern**: `<testAttribute><columnValue>` with `<valueSet>` for conditional code matching
- **Nested Test Logic**: Test attributes within restrictions for multi-layered filtering
- **SNOMED Refset Testing**: Test attributes using `<isRefset>true</isRefset>` value sets

## Advanced Workflow Patterns

### Multi-Criteria Group State Machines
- **NEXT Logic**: `<actionIfTrue>NEXT</actionIfTrue>` for conditional progression
- **REJECT/SELECT Inversion**: `<actionIfTrue>REJECT</actionIfTrue><actionIfFalse>SELECT</actionIfFalse>`
- **Complex State Flow**: Multiple criteria groups with different selection logic

### Population Criterion References (Report Chaining)
- **Pattern**: `<populationCriterion reportGuid="..." />` within criteria elements
- **Purpose**: Build complex reports by combining populations from other reports
- **Logic**: Supports OR logic to combine multiple report populations
- **Examples**: PSA monitoring register combines cancer monitoring + raised PSA populations

### Age-at-Event Processing
- **Dynamic Age Calculation**: `<column>AGE_AT_EVENT</column>` for event-specific age
- **Child/Adult Logic**: Age < 18 years vs Age >= 18 years for safeguarding
- **Healthcare Pathways**: Age-appropriate intervention routing

### Negation with Linked Criteria
- **Complex Exclusions**: `<negation>true</negation>` combined with `<linkedCriterion>`
- **Temporal Exclusions**: "Has monitoring BUT NOT if subsequent diagnosis exists"
- **Advanced Logic**: Negative relationships with date-based constraints

### Sequential Processing
- **Sequential Processing**: `<actionIfTrue>NEXT</actionIfTrue>` for conditional progression
- **Inverse Logic**: `<actionIfTrue>REJECT</actionIfTrue><actionIfFalse>SELECT</actionIfFalse>`
- **Multi-Stage Filtering**: Different criteria groups with different selection logic

## Report XML Structures (Distinct from Search XMLs)

### Report Folder Enterprise Structure
- **Container Element**: `<reportFolder>` for grouping related reports
- **Enterprise Level**: `<enterpriseReportingLevel>PSEUDO_IDENTIFYING</enterpriseReportingLevel>`
- **Multi-Organization**: Multiple `<association><organisation>guid</organisation></association>`
- **Population Control**: `<PopulationTypeId>PATIENT</PopulationTypeId>`
- **Enterprise Override**: `<IsEnterpriseSearchOverride>false</IsEnterpriseSearchOverride>`

### Report-Specific Elements
- **Anonymized Identifiers**: `<column>ANONYMISED_PATIENT_ID</column>` for privacy compliance
- **Version Control**: `<VersionIndependentGUID>` for cross-version compatibility
- **Quality Targets**: `<contractInformation><target>3</target>` for healthcare quality scoring
- **QOF Indicators**: `<qmasIndicator>PC</qmasIndicator>` for Quality and Outcomes Framework

### Report Dependencies
- **Population References**: `<populationCriterion reportGuid="..." />` to reference search populations
- **Report Hierarchies**: Parent-child relationships between reports
- **Search Integration**: Reports build upon search logic for data presentation

### List Report Column Sorting
- **Pattern**: `<sort><columnId>guid</columnId><direction>DESC</direction></sort>`
- **Purpose**: Multi-column sorting within List Report column groups
- **Usage**: Complex sorting on User Details, Concept ID, Date for organized output

## Document Metadata Parsing Patterns

### Creation Time and Author Information
- **Document Level**: `<creationTime>2025-09-10T14:46:45.6994382+01:00</creationTime>` (at enquiryDocument root)
- **Report Level**: `<creationTime>2025-01-30T12:39:07.3163132+00:00</creationTime>` (within individual report)
- **Author Name Format**: `<author><authorName>MCJIMMYFACE, Jimmy (Dr)</authorName></author>`
- **Author User ID Format**: `<author><userInRole>edec30d0-0cf3-4488-8fab-0b71a1af7f4c</userInRole></author>`

### Parsing Requirements
- **Creation Time**: Extract report-level creation time preferentially, fall back to document-level
- **Author Extraction**: Extract authorName when available, otherwise show userInRole GUID
- **Timestamp Format**: ISO 8601 format with timezone offset (+01:00, +00:00)

## Implementation Notes

### Namespace Handling
- **Default Namespace**: Elements without prefixes require fallback XPath
- **Prefixed Elements**: Standard `emis:` namespace for most elements
- **Mixed Documents**: Combination of prefixed and default namespace elements

### Performance Considerations
- **Memory Optimization**: Large file processing with streaming parsers
- **Cross-Table Joins**: Efficient relationship resolution
- **Complex Calculations**: Age and date arithmetic optimization

### Export Requirements
- **Source Attribution**: Search vs report origin tracking
- **Configurable Integration**: User-controlled report code inclusion
- **Filter Preservation**: Clinical code filtering independent of structure analysis

## Patient Demographics and Area-Based Filtering Patterns

### Lower Layer Super Output Area (LSOA) Filtering

EMIS supports patient demographics filtering using Office for National Statistics Lower Layer Super Output Areas for Index of Multiple Deprivation (IMD) analysis and population health studies. Despite the "LONDON" prefix in the column name, this system covers all LSOA areas across England and Wales.

#### Pattern Structure
```xml
<criteriaGroup>
  <definition>
    <memberOperator>OR</memberOperator>
    <criteria>
      <criterion>
        <id>49b44815-002d-4ab7-adc6-f17ab93bc275</id>
        <table>PATIENTS</table>
        <displayName>Patient Details</displayName>
        <negation>false</negation>
        <filterAttribute>
          <columnValue>
            <id>23e4e672-b3eb-4e9c-b6a0-8c5062ae416a</id>
            <column>LONDON_LOWER_AREA_2011</column>
            <displayName>Lower Layer Area (2011)</displayName>
            <inNotIn>IN</inNotIn>
            <singleValue>
              <variable>
                <value>E01006420</value>
              </variable>
            </singleValue>
          </columnValue>
        </filterAttribute>
      </criterion>
    </criteria>
    <!-- Additional criteria for each LSOA code -->
    <criteria>
      <criterion>
        <!-- Same criterion ID, different LSOA value -->
        <id>49b44815-002d-4ab7-adc6-f17ab93bc275</id>
        <table>PATIENTS</table>
        <filterAttribute>
          <columnValue>
            <column>LONDON_LOWER_AREA_2011</column>
            <inNotIn>IN</inNotIn>
            <singleValue>
              <variable>
                <value>E01018749</value>
              </variable>
            </singleValue>
          </columnValue>
        </filterAttribute>
      </criterion>
    </criteria>
  </definition>
  <actionIfTrue>SELECT</actionIfTrue>
  <actionIfFalse>REJECT</actionIfFalse>
</criteriaGroup>
```

### Key Characteristics
- **Shared Criterion ID**: Multiple criteria share the same criterion ID but contain different LSOA values
- **OR Logic**: `memberOperator>OR` allows inclusion of patients from any specified area
- **Variable Values**: LSOA codes stored as simple string variables (no temporal or numeric processing)
- **Column Type**: `LONDON_LOWER_AREA_2011` using 2011 Census boundaries (covers all England and Wales)

### LSOA Code Format
- **Pattern**: E followed by 8 digits (e.g., E01006420, E01033756) 
- **Geographic Scope**: Lower Layer Super Output Areas across England and Wales (2011 Census boundaries)
- **Coverage**: Nationwide LSOA codes despite "LONDON" in column name
- **Usage**: Index of Multiple Deprivation (IMD) studies, health inequality research, population health analysis

### Implementation Notes
- **Multiple Areas**: Each LSOA requires separate criterion within the same criteriaGroup
- **Performance**: OR logic with multiple patient demographics criteria may impact query performance on large datasets
- **Data Source**: LSOA codes derived from patient postcode data linked to ONS area boundaries

### Key Distinctions from Search XMLs
1. **Purpose**: Reports focus on data presentation vs searches focus on population identification
2. **Structure**: Enterprise reporting containers vs individual search logic
3. **Privacy**: Built-in anonymization vs direct patient identification
4. **Quality**: Integrated quality metrics vs clinical logic
5. **Scope**: Multi-organization vs single practice focus
